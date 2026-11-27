"""Score fresh verbatim ASR on full AMI recordings using manual references."""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .ami_disfluency import explicit_revision_references, repetition_references
from .ami_references import segment_gap_references, word_references
from .benchmark_features import benchmark
from .evaluate import recording_event_metrics
from .verbatim import (
    analyze_timestamped_words, level_gated_fillers, retimed_level_gated_fillers,
)


def write_report(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('recordings', nargs='+', type=Path, help='Full WAV tracks named MEETING.SLOT.wav')
    parser.add_argument('--model', required=True, help='Local CrisperWhisper Transformers snapshot')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-int8', action='store_true', help='use CTranslate2 CPU inference')
    parser.add_argument('--timing-method', choices=('attention', 'forced_aligner'),
                        default='attention')
    parser.add_argument('--event-cache', type=Path, help='optional local JSON with filler timestamps')
    args = parser.parse_args()
    if args.cpu_int8 and args.device != 'cpu':
        parser.error('--cpu-int8 requires CPU execution')
    if args.event_cache is not None and args.event_cache.resolve() == args.output.resolve():
        parser.error('--event-cache must differ from --output')
    if len({path.stem for path in args.recordings}) != len(args.recordings):
        parser.error('recording identifiers must be unique')

    import numpy as np
    import soundfile as sf
    import torch
    from crisperwhisper import CrisperWhisperModel
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(4)
    precision = 'int8' if args.cpu_int8 else 'float16' if args.device == 'cuda' else 'float32'
    backend = 'ct2' if args.cpu_int8 else 'transformers'
    model = CrisperWhisperModel(args.model, backend=backend, device=args.device,
                               compute_type=precision)
    vad = load_silero_vad()
    rows = []
    cached_events = {}
    diagnostics = []
    gated_rows = []
    retimed_rows = []
    repetition_rows = {'baseline': [], 'candidate': []}
    untimed_repetitions = 0
    untimed_revisions = 0
    longer_pause_rows = []
    tolerances = {'speaking_rate': 10, 'rate_changes': 15}
    with ZipFile(args.annotations) as archive:
        with archive.open('corpusResources/meetings.xml') as stream:
            meetings = ElementTree.parse(stream)
        speakers = {
            f"{meeting.attrib['observation']}.{speaker.attrib['nxt_agent']}": speaker.attrib['global_name']
            for meeting in meetings.iter('meeting') for speaker in meeting.findall('speaker')
        }
        for path in args.recordings:
            audio, sample_rate = sf.read(path, dtype='float32')
            if sample_rate != 16000 or audio.ndim != 1:
                parser.error(f'{path}: provide a mono 16 kHz complete track')
            duration = len(audio) / sample_rate
            ref = word_references(archive, path.stem, duration)
            ref['pauses'] = segment_gap_references(archive, path.stem, duration)
            speech = [(r['start'] / sample_rate, r['end'] / sample_rate)
                      for r in get_speech_timestamps(torch.from_numpy(np.ascontiguousarray(audio)),
                                                     vad, sampling_rate=sample_rate)]
            longer_speech = [
                (r['start'] / sample_rate, r['end'] / sample_rate)
                for r in get_speech_timestamps(torch.from_numpy(np.ascontiguousarray(audio)),
                                               vad, sampling_rate=sample_rate,
                                               min_silence_duration_ms=1000)
            ]
            longer_pause_rows.append({
                'duration_s': duration, 'reference': ref['pauses'],
                'predicted': [{'start_s': end, 'end_s': start}
                              for (_, end), (start, _) in zip(longer_speech, longer_speech[1:])
                              if start > end],
            })
            result = model.transcribe(audio, sr=sample_rate, language='en', word_timestamps=True,
                                      timing_method=args.timing_method)
            if (args.timing_method == 'forced_aligner'
                    and result.timing_method != 'forced_aligner'):
                raise RuntimeError(f'{path.stem}: the backend fell back from forced alignment')
            repetition_ref = repetition_references(archive, path.stem, duration)
            revision_ref = explicit_revision_references(archive, path.stem, duration)
            if revision_ref is not None:
                ref['revisions'] = revision_ref['events']
                untimed_revisions += revision_ref['excluded_without_valid_timing']
            features = analyze_timestamped_words(duration, speech, result.words or [],
                                                 repetition_candidate=repetition_ref is not None)
            if repetition_ref is not None:
                untimed_repetitions += repetition_ref['excluded_without_valid_timing']
                predicted = features['repetitions']
                for method, key in (('baseline', 'value'), ('candidate', 'research_candidate')):
                    repetition_rows[method].append({
                        'duration_s': duration, 'reference': repetition_ref['events'],
                        'predicted': [{k: event[k] for k in ('start_s', 'end_s')}
                                      for event in (predicted.get(key) or [])],
                    })
            detected = features['fillers']['value']
            if args.event_cache is not None:
                with path.open('rb') as media:
                    digest = hashlib.file_digest(media, 'sha256').hexdigest()
                cached_events[path.stem] = {'duration_s': duration, 'events': detected, 'sha256': digest}
                write_report(args.event_cache, cached_events)
            diagnostics.append({
                'duration_s': duration,
                'reference': [{**event, 'text': 'filler'} for label in ('um', 'uh')
                              for event in ref[label]],
                'predicted': [{**event, 'text': 'filler'} for event in (detected or [])],
            })
            rows.append({'id': path.stem, 'speaker': speakers[path.stem], 'duration_s': duration,
                         'features': features, 'reference': ref})
            gated = {'fillers': {**features['fillers'],
                                 'value': level_gated_fillers(detected, audio, sample_rate)}}
            gated_rows.append({**rows[-1], 'features': gated,
                               'reference': {label: ref[label] for label in ('um', 'uh')}})
            retimed = retimed_level_gated_fillers(detected, audio, sample_rate)
            retimed_rows.append({**gated_rows[-1], 'features': {
                'fillers': {**features['fillers'], 'value': retimed}
            }})
            report = {
                'model': args.model,
                'backend': backend,
                'precision': precision,
                'timing_method': args.timing_method,
                'complete': len(rows) == len(args.recordings),
                'pooled': benchmark(rows, tolerances),
                'level_gated_filler_candidate': benchmark(gated_rows, tolerances),
                'retimed_filler_candidate': benchmark(retimed_rows, tolerances),
                'longer_silence_pause_candidate': recording_event_metrics(longer_pause_rows),
                'repetition_timing_comparison': {
                    method: recording_event_metrics(records) if records else None
                    for method, records in repetition_rows.items()
                },
                'excluded_repetition_references_without_timing': untimed_repetitions,
                'revision_reference_scope': 'explicit editing terms',
                'excluded_revision_references_without_timing': untimed_revisions,
                'untyped_filler_diagnostic': recording_event_metrics(diagnostics),
                'per_recording': {
                    row['id']: benchmark([row], tolerances) for row in rows
                },
            }
            write_report(args.output, report)
            print(f'Analyzed {path.stem}: {duration:.1f}s', flush=True)


if __name__ == '__main__':
    main()

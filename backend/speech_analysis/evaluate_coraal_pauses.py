"""Compare pause settings on explicitly annotated CORAAL interview excerpts."""

import argparse
import csv
import io
import json
import re
import tarfile
from pathlib import Path

from .evaluate import recording_event_metrics

PAUSE = re.compile(r'\(pause [\d.]+\)', re.IGNORECASE)
SETTINGS = {
    'default_silero': (.50, 100, 30),
    'one_second_baseline': (.50, 1000, 30),
    'short_silence_candidate': (.62, 180, 0),
}
EXCERPT_SECONDS = 30
SAMPLE_RATE = 16000


def annotated_windows(transcript, speaker):
    speech, other, pauses = [], [], []
    for row in csv.DictReader(io.StringIO(transcript), delimiter='\t'):
        try:
            start, end = float(row['StTime']), float(row['EnTime'])
        except (ValueError, TypeError):
            continue
        if PAUSE.fullmatch(row['Content'].strip()):
            if row['Spkr'] == speaker and end - start >= .30:
                pauses.append((start, end))
        else:
            (speech if row['Spkr'] == speaker else other).append((start, end))

    windows = []
    for start, _ in speech:
        if windows and start < windows[-1][0] + EXCERPT_SECONDS:
            continue
        end = start + EXCERPT_SECONDS
        if any(a < end and b > start for a, b in other):
            continue
        if any(a < start < b or a < end < b for a, b in (*speech, *pauses)):
            continue
        reference = [{'start_s': a - start, 'end_s': b - start}
                     for a, b in pauses if start <= a < b <= end]
        speech_seconds = sum(max(0., min(b, end) - max(a, start)) for a, b in speech)
        if len(reference) >= 3 and speech_seconds >= EXCERPT_SECONDS / 2:
            windows.append((start, reference))
            if len(windows) == 2:
                break
    return windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('transcripts', type=Path, help='CORAAL textfiles tar.gz')
    parser.add_argument('archives', type=Path, nargs='+', help='CORAAL audio part tar.gz files')
    parser.add_argument('--exclude-speaker', action='append', default=[])
    args = parser.parse_args()

    import numpy as np
    import soundfile as sf
    import torch
    from scipy.signal import resample_poly
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(1)
    model = load_silero_vad()
    results = {name: [] for name in SETTINGS}
    speakers = set()
    selection = []
    seen_records = set()
    with tarfile.open(args.transcripts) as text:
        transcripts = {Path(member.name).stem: member for member in text.getmembers()
                       if member.isfile() and member.name.endswith('.txt')}
        for path in args.archives:
            with tarfile.open(path, 'r|gz') as audio:
                for member in audio:
                    if not member.isfile() or not member.name.endswith('.wav'):
                        continue
                    recording = Path(member.name).stem
                    speaker = recording.rsplit('_', 1)[0]
                    if recording in seen_records or speaker in args.exclude_speaker:
                        continue
                    seen_records.add(recording)
                    transcript = text.extractfile(transcripts[recording]).read().decode('utf-8-sig')
                    windows = annotated_windows(transcript, speaker)
                    if not windows:
                        continue
                    waveform, rate = sf.read(io.BytesIO(audio.extractfile(member).read()), dtype='float32')
                    if waveform.ndim == 2:
                        waveform = waveform.mean(axis=1)
                    for start, references in windows:
                        stop = round((start + EXCERPT_SECONDS) * rate)
                        if stop > len(waveform):
                            continue
                        clip = waveform[round(start * rate):stop]
                        if rate != SAMPLE_RATE:
                            clip = resample_poly(clip, SAMPLE_RATE, rate)
                        tensor = torch.from_numpy(np.ascontiguousarray(clip))
                        for name, (confidence, silence, padding) in SETTINGS.items():
                            speech = get_speech_timestamps(tensor, model, sampling_rate=SAMPLE_RATE,
                                                           threshold=confidence, min_silence_duration_ms=silence,
                                                           speech_pad_ms=padding)
                            predictions = [{'start_s': a['end'] / SAMPLE_RATE, 'end_s': b['start'] / SAMPLE_RATE}
                                           for a, b in zip(speech, speech[1:])
                                           if b['start'] - a['end'] >= .30 * SAMPLE_RATE]
                            results[name].append({'duration_s': len(clip) / SAMPLE_RATE,
                                                  'reference': references, 'predicted': predictions})
                        speakers.add(speaker)
                        selection.append({'recording': recording, 'start_s': start, 'references': len(references)})
    if not selection:
        parser.error('no annotated single-speaker excerpts met the selection rules')
    print(json.dumps({'speakers': len(speakers), 'excerpts': selection,
                      'results': {name: recording_event_metrics(rows) for name, rows in results.items()}},
                     allow_nan=False, indent=2))


if __name__ == '__main__':
    main()

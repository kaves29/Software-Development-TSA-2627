"""Compare pause and energy estimates on annotated English excerpts from SBCSAE."""

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from .acoustics import energy_variation
from .analysis import TOKEN
from .benchmark_features import benchmark
from .evaluate import recording_event_metrics

ANNOTATION = re.compile(r'^\s*(\d+\.\d+)\s+(\d+\.\d+)\t([^\t]*)\t(.*)$')
TRANSCRIPTION_MARKUP = re.compile(r'\([^)]*\)|<[^>]*>|\{[^}]*\}')
MINIMUM_GAP_S = .30
SAMPLE_RATE = 16000


def annotated_excerpt(path, start, duration):
    """Return one annotated speaker and merged spans containing lexical speech."""
    speaker = ''
    excerpt_speakers = set()
    spans = []
    end = start + duration
    for line in path.read_text(encoding='latin1').splitlines():
        row = ANNOTATION.fullmatch(line)
        if row is None:
            continue
        left, right, name, transcript = row.groups()
        speaker = name.strip() or speaker
        left, right = float(left), float(right)
        if right <= left or right <= start or left >= end:
            continue
        if not TOKEN.search(TRANSCRIPTION_MARKUP.sub(' ', transcript).lower()):
            continue
        if not start <= left < right <= end:
            raise ValueError(f'{path.name}: excerpt cuts through an annotated utterance')
        excerpt_speakers.add(speaker)
        spans.append((left - start, right - start))
    if len(excerpt_speakers) != 1 or '' in excerpt_speakers:
        raise ValueError(f'{path.name}: excerpt must contain one identified speaker')
    merged = []
    for left, right in sorted(spans):
        if merged and left <= merged[-1][1]:
            merged[-1] = merged[-1][0], max(right, merged[-1][1])
        else:
            merged.append((left, right))
    return excerpt_speakers.pop(), merged


def internal_gaps(spans):
    return [{'start_s': left_end, 'end_s': right_start}
            for (_, left_end), (right_start, _) in zip(spans, spans[1:])
            if right_start - left_end >= MINIMUM_GAP_S]


def excerpt_spec(value):
    fields = value.split(':')
    try:
        recording, start, duration = fields[0], float(fields[1]), float(fields[2])
    except (IndexError, ValueError) as exc:
        raise argparse.ArgumentTypeError('expected SBC123:START_SECONDS:DURATION_SECONDS') from exc
    if (len(fields) != 3 or not re.fullmatch(r'SBC\d{3}', recording)
            or not math.isfinite(start) or start < 0 or not 0 < duration <= 240):
        raise argparse.ArgumentTypeError('provide an SBC recording ID, nonnegative start, and duration up to 240 s')
    return recording, start, duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directory with paired SBC WAV and TRN files')
    parser.add_argument('excerpts', type=excerpt_spec, nargs='+')
    args = parser.parse_args()

    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(2)
    model = load_silero_vad()
    pause_rows = {'silero_default': [], 'silero_one_second': []}
    energy_rows = {name: [] for name in pause_rows}
    for recording, start, duration in args.excerpts:
        source = args.directory / recording
        speaker, reference = annotated_excerpt(source.with_suffix('.trn'), start, duration)
        raw = subprocess.check_output([
            'ffmpeg', '-nostdin', '-v', 'error', '-ss', str(start), '-i', str(source.with_suffix('.wav')),
            '-t', str(duration), '-ac', '1', '-ar', str(SAMPLE_RATE), '-f', 'f32le', '-',
        ], timeout=120)
        audio = np.frombuffer(raw, dtype='<f4').copy()
        if abs(len(audio) / SAMPLE_RATE - duration) > .001:
            raise ValueError(f'{recording}: decoded excerpt differs from the requested duration')
        expected_energy = energy_variation(audio, SAMPLE_RATE, reference)
        for name, minimum_silence in [('silero_default', 100), ('silero_one_second', 1000)]:
            detected = get_speech_timestamps(torch.from_numpy(audio), model, sampling_rate=SAMPLE_RATE,
                                             min_silence_duration_ms=minimum_silence)
            spans = [(span['start'] / SAMPLE_RATE, span['end'] / SAMPLE_RATE) for span in detected]
            pause_rows[name].append({'duration_s': duration, 'reference': internal_gaps(reference),
                                     'predicted': internal_gaps(spans)})
            energy_rows[name].append({
                'id': f'{recording}:{start}', 'speaker': f'{recording}:{speaker}', 'duration_s': duration,
                'reference': {'energy_variation': expected_energy},
                'features': {'energy_variation': {'value': energy_variation(audio, SAMPLE_RATE, spans)}},
            })
    report = {
        'pauses': {name: recording_event_metrics(rows) for name, rows in pause_rows.items()},
        'energy_variation': {
            name: benchmark(rows, {'energy_variation': 2})['features']['energy_variation']
            for name, rows in energy_rows.items()
        },
    }
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

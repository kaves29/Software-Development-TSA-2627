"""Compare pause and energy estimates on annotated monologues."""

import argparse
import csv
import json
import subprocess
import warnings
from pathlib import Path
from zipfile import ZipFile

from .acoustics import energy_variation
from .benchmark_features import benchmark
from .evaluate import recording_event_metrics


def annotation_rows(archive, name):
    files = [path for path in archive.namelist() if Path(path).name == f'{name}_events.tsv']
    if len(files) != 1:
        raise ValueError(f'{name}: expected exactly one events table')
    return csv.DictReader(archive.read(files[0]).decode('utf-8-sig').splitlines(), delimiter='\t')


def pause_references(archive, name, duration):
    events = []
    collapsed = 0
    for row in annotation_rows(archive, name):
        if row['event_type'] != 'pause':
            continue
        start, length = float(row['onset']), float(row['duration'])
        if not 0 <= start <= start + length <= duration + .02:
            raise ValueError(f'{name}: invalid pause timing {start}, {length}')
        if length == 0:
            collapsed += 1
            continue
        events.append({'start_s': start, 'end_s': start + length})
    if collapsed:
        warnings.warn(f'{name}: omitted {collapsed} zero-duration pause labels', RuntimeWarning)
    return events


def annotated_speech(archive, name, gaps):
    words = [(float(row['onset']), float(row['duration']))
             for row in annotation_rows(archive, name) if row['event_type'] == 'word']
    if not words:
        raise ValueError(f'{name}: no word annotations')
    start = min(onset for onset, _ in words)
    end = max(onset + duration for onset, duration in words)
    spans = []
    for gap in sorted(gaps, key=lambda item: item['start_s']):
        a, b = gap['start_s'], gap['end_s']
        if b <= start or a >= end:
            continue
        if a > start:
            spans.append((start, a))
        start = max(start, b)
    if start < end:
        spans.append((start, end))
    return spans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('recordings', type=Path, nargs='+')
    args = parser.parse_args()

    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    rate = 16000
    torch.set_num_threads(2)
    model = load_silero_vad()
    modes = {'default': (100, 30), 'short_gap': (48, 0)}
    results = {name: {} for name in modes}
    energy = {name: [] for name in ('default', 'short_gap', 'short_gap_trimmed')}
    with ZipFile(args.annotations) as archive:
        for path in args.recordings:
            if path.stem in results['default']:
                parser.error(f'duplicate recording: {path.stem}')
            raw = subprocess.check_output([
                'ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-vn',
                '-ac', '1', '-ar', str(rate), '-f', 'f32le', '-',
            ], timeout=120)
            audio = torch.from_numpy(np.frombuffer(raw, dtype='<f4').copy())
            duration = len(audio) / rate
            reference = pause_references(archive, path.stem, duration)
            expected_energy = energy_variation(audio.numpy(), rate,
                                               annotated_speech(archive, path.stem, reference))
            for name, (gap, pad) in modes.items():
                speech = get_speech_timestamps(audio, model, sampling_rate=rate,
                                               min_silence_duration_ms=gap,
                                               speech_pad_ms=pad)
                predicted = [{'start_s': prev['end'] / rate, 'end_s': curr['start'] / rate}
                             for prev, curr in zip(speech, speech[1:])
                             if prev['end'] < curr['start']]
                results[name][path.stem] = {'duration_s': duration, 'reference': reference,
                                            'predicted': predicted}
                spans = [(r['start'] / rate, r['end'] / rate) for r in speech]
                candidates = {name: spans}
                if name == 'short_gap':
                    candidates['short_gap_trimmed'] = [(a + .15, b - .15) for a, b in spans
                                                        if b - a >= .40]
                for method, selected in candidates.items():
                    value = energy_variation(audio.numpy(), rate, selected)
                    energy[method].append({
                        'id': path.stem, 'speaker': path.stem.split('_')[1],
                        'duration_s': duration,
                        'reference': {'energy_variation': expected_energy},
                        'features': {'energy_variation': {'value': value}},
                    })
    pauses = {
        name: {'pooled': recording_event_metrics(list(rows.values())),
               'per_recording': {key: recording_event_metrics([row])
                                 for key, row in rows.items()}}
        for name, rows in results.items()
    }
    print(json.dumps({
        'pauses': pauses,
        'energy_variation': {
            method: benchmark(rows, {'energy_variation': 2})['features']['energy_variation']
            for method, rows in energy.items()
        },
    }, indent=2))


if __name__ == '__main__':
    main()

"""Compare headset levels to estimate pauses for a known AMI speaker."""

import argparse
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .ami_references import segment_gap_references
from .evaluate import recording_event_metrics

RATE = 16000
FRAME = 320


def channel_levels(path):
    raw = subprocess.check_output([
        'ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-ac', '1',
        '-ar', str(RATE), '-f', 'f32le', '-',
    ], timeout=120)
    audio = np.frombuffer(raw, dtype='<f4')
    frames = audio[:len(audio) // FRAME * FRAME].reshape(-1, FRAME)
    if len(frames) < 5:
        raise ValueError(f'Empty or too-short headset recording: {path}')
    power = np.mean(frames ** 2, axis=1)
    smooth_power = np.convolve(power, np.full(5, .2), mode='same')
    return len(audio) / RATE, 10 * np.log10(smooth_power + 1e-10)


def target_speech_spans(target, peers):
    """Estimate target-dominant runs on synchronized headset channels."""
    if not peers:
        raise ValueError('at least one synchronous peer channel is required')
    duration, own = channel_levels(target)
    other = [channel_levels(path)[1] for path in peers]
    if any(abs(len(channel) - len(own)) > 2 for channel in other):
        raise ValueError('Headset recordings have unequal durations')
    length = min(len(own), *(len(channel) for channel in other))
    own = own[:length]
    levels = np.stack([own, *(channel[:length] for channel in other)])
    relative = levels - np.quantile(levels, .95, axis=1, keepdims=True)
    active = (relative[0] >= relative[1:].max(axis=0)) & (relative[0] >= -26)
    boundaries = np.flatnonzero(np.diff(np.r_[False, active, False]))
    spans = [(a, b) for a, b in zip(boundaries[::2], boundaries[1::2]) if b - a >= 10]
    return duration, [(float(a * FRAME / RATE), float(b * FRAME / RATE)) for a, b in spans]


def predict(target, peers):
    duration, spans = target_speech_spans(target, peers)
    pauses = [{'start_s': end, 'end_s': start}
              for (_, end), (start, _) in zip(spans, spans[1:]) if start - end >= 1 - 1e-9]
    return duration, pauses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('target', type=Path, help='target WAV named MEETING.SLOT.wav')
    parser.add_argument('peers', type=Path, nargs='+', help='synchronous WAVs from other headsets')
    args = parser.parse_args()
    paths = [path.resolve() for path in (args.target, *args.peers)]
    if len(set(paths)) != len(paths):
        parser.error('target and peer channels must be distinct')
    duration, events = predict(args.target, args.peers)
    with ZipFile(args.annotations) as archive:
        reference = segment_gap_references(archive, args.target.stem, duration)
    print(json.dumps(recording_event_metrics([
        {'duration_s': duration, 'reference': reference, 'predicted': events},
    ]), indent=2))


if __name__ == '__main__':
    main()

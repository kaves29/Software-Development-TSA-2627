"""Score a fixed FFmpeg silence baseline on complete AMI headset tracks."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

from .ami_references import segment_gap_references
from .evaluate import recording_event_metrics


def silence_events(path, duration, threshold_db, minimum_seconds):
    result = subprocess.run([
        'ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-vn',
        '-af', f'silencedetect=n={threshold_db}dB:d={minimum_seconds}',
        '-f', 'null', '-',
    ], check=True, capture_output=True, text=True, timeout=120)
    events = []
    start = None
    for boundary, timestamp in re.findall(
        r'silence_(start|end): (-?\d+(?:\.\d+)?)', result.stderr
    ):
        time = float(timestamp)
        if boundary == 'start':
            start = time
        elif start is not None:
            if 0 < start < time < duration - .01:
                events.append({'start_s': start, 'end_s': time})
            start = None
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('recordings', nargs='+', type=Path, help='WAVs named MEETING.SLOT.wav')
    parser.add_argument('--threshold-db', type=float, default=-40)
    parser.add_argument('--minimum-seconds', type=float, default=1.5)
    args = parser.parse_args()
    rows = {}
    with ZipFile(args.annotations) as archive:
        for path in args.recordings:
            if path.stem in rows:
                parser.error(f'duplicate recording: {path.stem}')
            duration = float(subprocess.check_output([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'csv=p=0', str(path),
            ], timeout=30))
            rows[path.stem] = {
                'duration_s': duration,
                'reference': segment_gap_references(archive, path.stem, duration),
                'predicted': silence_events(path, duration, args.threshold_db, args.minimum_seconds),
            }
    print(json.dumps({
        'threshold_db': args.threshold_db, 'minimum_seconds': args.minimum_seconds,
        'pooled': recording_event_metrics(list(rows.values())),
        'per_recording': {name: recording_event_metrics([row]) for name, row in rows.items()},
    }, indent=2))


if __name__ == '__main__':
    main()

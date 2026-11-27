"""Explore Speakly wrist-motion coverage on GESRes annotated gesture clips.

This is an exploratory label comparison, not an estimate of gesture accuracy:
GESRes speed labels and Speakly's rapid-motion threshold have different definitions.
"""

import argparse
import csv
import json
import subprocess
import tempfile
from pathlib import Path

from . import video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--video-id', required=True, help='Exact id column in GESRes CSV')
    parser.add_argument('--pose-model', type=Path, required=True)
    parser.add_argument('--fps', type=int, choices=(5, 10), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    video.FPS = args.fps  # Comparison is limited to the speed-normalized rapid-motion field.
    with args.annotations.open(encoding='utf-8-sig', newline='') as source:
        rows = [row for row in csv.DictReader(source) if row['id'] == args.video_id]
    if not rows:
        parser.error('video id has no annotation rows')
    results = []
    with tempfile.TemporaryDirectory() as temp:
        for index, row in enumerate(rows):
            start, end = float(row['start_t']), float(row['end_t'])
            if not 0 <= start < end:
                raise ValueError(f'invalid annotation interval at row {index + 1}')
            clip = Path(temp) / f'{index}.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(start),
                            '-i', str(args.video), '-t', str(end - start), '-an',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-y', str(clip)],
                           check=True, timeout=30)
            output = video.analyze_video(clip, args.pose_model)
            results.append({'index': index + 1, 'start_s': start, 'end_s': end,
                            'speed_label': row['speed'],
                            'rapid_motion': output['features']['rapid_gesture'],
                            'frames': output['quality']['frames'],
                            'pose_frames': output['quality']['pose_frames']})
    args.output.write_text(json.dumps({'fps': args.fps, 'results': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()

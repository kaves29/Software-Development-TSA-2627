"""Explore Speakly wrist-motion measurements on GESRes annotated gesture clips.

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
    parser.add_argument('--resolution', type=int, choices=(384, 640), default=384,
                        help='Research-only square processing resolution')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--crop-left-pixels', type=int, default=0, help='Optional research-only crop in source pixels')
    args = parser.parse_args()
    if args.crop_left_pixels < 0:
        parser.error('crop-left-pixels cannot be negative')
    video.FPS = args.fps  # Per-frame hand movement is compared only within the same fps.
    video.WIDTH = video.HEIGHT = args.resolution
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
            command = ['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(start),
                       '-i', str(args.video), '-t', str(end - start), '-an']
            if args.crop_left_pixels:
                command += ['-vf', f'crop=iw-{args.crop_left_pixels}:ih:{args.crop_left_pixels}:0']
            subprocess.run(command + ['-c:v', 'libx264', '-preset', 'ultrafast', '-y', str(clip)],
                           check=True, timeout=30)
            output = video.analyze_video(clip, args.pose_model)
            results.append({'index': index + 1, 'start_s': start, 'end_s': end,
                            'speed_label': row['speed'], 'hand_label': row['handedness'],
                            'left_hand_motion': output['features']['left_hand_motion'],
                            'right_hand_motion': output['features']['right_hand_motion'],
                            'rapid_motion': output['features']['rapid_gesture'],
                            'frames': output['quality']['frames'],
                            'pose_frames': output['quality']['pose_frames']})
    args.output.write_text(json.dumps({'video_id': args.video_id, 'fps': args.fps,
                                      'crop_left_pixels': args.crop_left_pixels, 'resolution': args.resolution,
                                      'results': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()

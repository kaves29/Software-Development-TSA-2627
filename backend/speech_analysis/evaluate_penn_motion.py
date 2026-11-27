"""Measure temporal pose components against Penn Action's annotated test frames."""

import argparse
import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .benchmark_features import benchmark
from .video import FPS, HEIGHT, WIDTH, observations

PENN_JOINT_MAP = (0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)
MOTION_FEATURES = ('torso_sway', 'vertical_motion', 'head_motion', 'left_hand_motion',
                   'right_hand_motion', 'hand_asymmetry')
TOLERANCES = {**dict.fromkeys(MOTION_FEATURES, .05), 'pose_coverage': .10}
FRAME_STRIDE = 6
INTERPOLATED_JOINTS = (0, 15, 16)


def prepare_frame(path, annotation):
    import cv2

    data = cv2.imread(str(path))
    if data is None:
        raise ValueError(f'cannot decode {path}')
    height, width = data.shape[:2]
    scale = min(HEIGHT / height, WIDTH / width)
    scaled_height, scaled_width = round(height * scale), round(width * scale)
    top, left = (HEIGHT - scaled_height) // 2, (WIDTH - scaled_width) // 2
    rgb = cv2.cvtColor(cv2.resize(data, (scaled_width, scaled_height)), cv2.COLOR_BGR2RGB)
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame[top:top + scaled_height, left:left + scaled_width] = rgb

    index = int(path.stem) - 1
    visible = annotation['visibility'][index]
    if np.count_nonzero(visible) < 5:
        return frame, None
    landmarks = [SimpleNamespace(x=0., y=0., visibility=0., presence=0.) for _ in range(33)]
    for column, landmark_index in enumerate(PENN_JOINT_MAP):
        x = float(annotation['x'][index, column])
        y = float(annotation['y'][index, column])
        confidence = float(visible[column] != 0)
        landmarks[landmark_index] = SimpleNamespace(
            x=(x * scaled_width / width + left) / WIDTH,
            y=(y * scaled_height / height + top) / HEIGHT,
            visibility=confidence, presence=confidence,
        )
    return frame, landmarks


def interpolate_landmarks(poses):
    """Fill one low-confidence sample when the same joint is visible on both sides."""
    result = list(poses)
    for index in range(1, len(poses) - 1):
        left, current, right = poses[index - 1:index + 2]
        if any(frame is None for frame in (left, current, right)):
            continue
        result[index] = list(current)
        for joint in INTERPOLATED_JOINTS:
            prior, missing, following = left[joint], current[joint], right[joint]
            if (min(missing.visibility, missing.presence) < .65
                    and min(prior.visibility, prior.presence,
                            following.visibility, following.presence) >= .65):
                result[index][joint] = SimpleNamespace(
                    x=(prior.x + following.x) / 2, y=(prior.y + following.y) / 2,
                    presence=.65, visibility=.65,
                )
    return result


def left_hand_motion_candidate(poses):
    """Measure wrist displacement with one shoulder scale per frame pair."""
    previous = None
    movements = []
    for pose in poses:
        current = None
        if pose is not None:
            a, b, wrist = (pose[index] for index in (11, 12, 15))
            if all(min(joint.visibility, joint.presence) >= threshold
                   for joint, threshold in ((a, .65), (b, .65), (wrist, .50))):
                left, right, hand = (np.array((joint.x, joint.y)) for joint in (a, b, wrist))
                width = np.linalg.norm(left - right)
                if width >= .05:
                    current = hand - (left + right) / 2, width
        if current is not None and previous is not None:
            offset, width = current
            prior_offset, prior_width = previous
            movements.append(np.linalg.norm(offset - prior_offset) / ((width + prior_width) / 2))
        previous = current
    if len(movements) < 3:
        return None
    # Freeze the linear calibration selected on Penn Action's training subset.
    return float(.8 * np.median(movements) + .02)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path, help='Directory with Penn Action labels/ and frames/')
    parser.add_argument('pose_model', type=Path)
    parser.add_argument('--sample-count', type=int, default=180)
    parser.add_argument('--seed', type=int, default=20261127)
    args = parser.parse_args()
    if not 1 <= args.sample_count <= 2326:
        parser.error('sample count must be between 1 and 2326')

    import mediapipe as mp
    from scipy.io import loadmat

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.pose_model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1,
    )
    ids = sorted(random.Random(args.seed).sample(range(1, 2327), args.sample_count))
    rows = []
    interpolated_rows = []
    left_hand_rows = []
    total_frames = positive_frames = matched_frames = 0
    for number in ids:
        clip_id = f'{number:04d}'
        annotation = loadmat(args.dataset / 'labels' / f'{clip_id}.mat', squeeze_me=True)
        if int(annotation['train']) != -1:
            continue
        frame_directory = args.dataset / 'frames' / clip_id
        files = [frame_directory / f'{index:06d}.jpg'
                 for index in range(1, int(annotation['nframes']) + 1, FRAME_STRIDE)]
        if len(files) < 6:
            continue
        reference, predicted = [], []
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            for index, path in enumerate(files):
                frame, landmarks = prepare_frame(path, annotation)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                result = detector.detect_for_video(image, index * 1000 // FPS).pose_landmarks
                prediction = result[0] if result else None
                reference.append(landmarks)
                predicted.append(prediction)
                total_frames += 1
                positive_frames += landmarks is not None
                matched_frames += (landmarks is None) == (prediction is None)
        target = {name: item['value'] for name, item in observations(reference).items()
                  if name in TOLERANCES}
        target['pose_coverage'] = sum(landmarks is not None for landmarks in reference) / len(files)
        rows.append({'id': clip_id, 'speaker': clip_id, 'duration_s': len(files) / FPS,
                     'features': observations(predicted), 'reference': target})
        interpolated_rows.append({**rows[-1], 'features': observations(interpolate_landmarks(predicted))})
        left_hand_rows.append({**rows[-1], 'features': {
            'left_hand_motion': {'value': left_hand_motion_candidate(predicted)},
        }})

    if not rows:
        parser.error('no held-out clips in the sampled subset')
    def motion_scores(recordings):
        result = benchmark(recordings, TOLERANCES)['features']
        return {name: {k: v for k, v in result[name].items() if k != 'speakers'}
                for name in TOLERANCES}

    print(json.dumps({
        'clips': len(rows),
        'frames': total_frames,
        'frames_with_at_least_five_visible_reference_joints': positive_frames,
        'pose_frame_agreement': matched_frames / total_frames,
        'features': motion_scores(rows),
        'interpolated_features': motion_scores(interpolated_rows),
        'left_hand_motion_candidate': benchmark(left_hand_rows, TOLERANCES)['features']['left_hand_motion'],
    }, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

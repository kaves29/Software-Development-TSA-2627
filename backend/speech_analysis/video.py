"""Camera-relative movement observations from MediaPipe Pose landmarks."""

import argparse
import json
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path

import numpy as np

WIDTH, HEIGHT, FPS = 384, 384, 5
NAMES = ('shoulder_tilt', 'lateral_lean', 'torso_sway', 'vertical_motion',
         'head_turn_proxy', 'head_motion', 'left_hand_motion', 'right_hand_motion',
         'hand_asymmetry', 'gesture_span', 'rapid_gesture', 'hands_together',
         'hand_near_face', 'wrist_visibility', 'pose_coverage')


def observations(frames):
    result = {name: {'status': 'insufficient_evidence', 'value': None} for name in NAMES}
    values = {name: [] for name in NAMES}
    previous = {}
    for pose in frames:
        current = {}
        values['pose_coverage'].append(float(pose is not None))
        if pose is not None:
            def point(index):
                item = pose[index]
                if min(item.visibility, item.presence) >= .65:
                    return np.array([item.x, item.y])

            left, right = point(11), point(12)
            if left is not None and right is not None:
                center = (left + right) / 2
                scale = np.linalg.norm(left - right)
                if scale >= .05:
                    current['center'] = center
                    values['shoulder_tilt'].append(abs(left[1] - right[1]) / scale)
                    hips = [point(23), point(24)]
                    if all(p is not None for p in hips):
                        values['lateral_lean'].append(abs(center[0] - np.mean(hips, axis=0)[0]) / scale)
                    nose = point(0)
                    if nose is not None:
                        current['head'] = (nose - center) / scale
                    ears = [point(7), point(8)]
                    if nose is not None and all(p is not None for p in ears):
                        values['head_turn_proxy'].append(nose_ear_asymmetry(nose, ears))
                    for side, index in [('left', 15), ('right', 16)]:
                        wrist = point(index)
                        if wrist is not None:
                            current[side] = (wrist - center) / scale
                    wrists = [current[side] for side in ('left', 'right') if side in current]
                    values['wrist_visibility'].append(len(wrists) / 2)
                    if wrists and 'head' in current:
                        values['hand_near_face'].append(float(any(
                            np.linalg.norm(wrist - current['head']) <= .35 for wrist in wrists)))
                    tracked = [side for side in ('left', 'right') if side in current and side in previous]
                    if tracked:
                        values['rapid_gesture'].append(float(any(
                            np.linalg.norm(current[side] - previous[side]) * FPS >= 2
                            for side in tracked)))
                    if 'left' in current and 'right' in current:
                        values['hands_together'].append(float(
                            np.linalg.norm(current['left'] - current['right']) <= .25))
                        values['gesture_span'].append(np.linalg.norm(current['left'] - current['right']))
                        if all(side in previous for side in ('left', 'right')):
                            values['hand_asymmetry'].append(abs(
                                np.linalg.norm(current['left'] - previous['left']) -
                                np.linalg.norm(current['right'] - previous['right'])))
                    if 'center' in previous:
                        delta = abs(center - previous['center']) / scale
                        values['torso_sway'].append(delta[0])
                        values['vertical_motion'].append(delta[1])
                    for key, name in [('head', 'head_motion'), ('left', 'left_hand_motion'),
                                      ('right', 'right_hand_motion')]:
                        if key in current and key in previous:
                            values[name].append(np.linalg.norm(current[key] - previous[key]))
        previous = current
    for name, measurements in values.items():
        if len(measurements) >= 5:
            fraction = name in {'rapid_gesture', 'hands_together', 'hand_near_face',
                                'wrist_visibility', 'pose_coverage'}
            if name == 'pose_coverage' and not any(measurements):
                continue
            aggregate = np.mean if fraction else np.median
            result[name] = {'status': 'experimental', 'value': round(float(aggregate(measurements)), 4),
                            'valid_frames': len(measurements)}
    return result


def nose_ear_asymmetry(nose, ears):
    distances = [np.linalg.norm(nose - ear) for ear in ears]
    return float(abs(distances[0] - distances[1]) / max(sum(distances), .01))


def absolute_face_yaw(matrix):
    """Estimate absolute head turn in degrees from the face transform."""
    matrix = np.asarray(matrix)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        return None
    horizontal, forward = matrix[0, 2], matrix[2, 2]
    if np.hypot(horizontal, forward) < 1e-6:
        return None
    return float(abs(np.degrees(np.arctan2(horizontal, forward))))


def proximity_intervals(frames):
    """Find sustained proximity, breaking tracks when either landmark is missing."""
    intervals = []
    start = None
    for index in range(len(frames) + 1):
        near = index < len(frames) and frames[index]['fingertip_near_face'] is True
        if near and start is None:
            start = index
        elif not near and start is not None:
            if index - start >= 3:
                intervals.append({'start_s': frames[start]['time_s'], 'end_s': round(index / FPS, 3)})
            start = None
    return intervals


def observed_proximity_returns(frames, intervals):
    """Count returns only after sustained visible separation."""
    returns = 0
    for prior, current in zip(intervals, intervals[1:]):
        separated = 0
        for frame in frames[round(prior['end_s'] * FPS):round(current['start_s'] * FPS)]:
            separated = separated + 1 if frame['fingertip_near_face'] is False else 0
            if separated >= 3:
                returns += 1
                break
    return returns


def background_shift(previous, current, pose):
    """Estimate camera movement using tracked points outside the detected person."""
    import cv2

    if pose is None:
        return None
    visible = [(p.x, p.y) for p in pose if p.visibility >= .65 and p.presence >= .65]
    if not visible:
        return None
    h, w = previous.shape
    bounds = np.array(visible) * [w, h]
    x0, y0 = np.maximum(0, bounds.min(axis=0).astype(int) - 20)
    x1, y1 = bounds.max(axis=0).astype(int) + 21
    mask = np.full((h, w), 255, np.uint8)
    mask[y0:y1, x0:x1] = 0
    points = cv2.goodFeaturesToTrack(previous, 80, .02, 8, mask=mask)
    if points is None:
        return None
    moved, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points, None)
    if moved is None or status is None:
        return None
    valid = status.ravel() == 1
    original = points[valid].reshape(-1, 2)
    tracked = moved[valid].reshape(-1, 2)
    if len(original) < 8:
        return None
    transform, inliers = cv2.estimateAffinePartial2D(original, tracked, method=cv2.RANSAC,
                                                      ransacReprojThreshold=2)
    if transform is None or inliers is None or inliers.sum() < max(8, .7 * len(original)):
        return None
    background = original[inliers.ravel() == 1]
    if np.any(np.ptp(background, axis=0) < np.array([w, h]) * .25):
        return None
    projected = background @ transform[:, :2].T + transform[:, 2]
    return float(np.median(np.linalg.norm(projected - background, axis=1)))


def analyze_video(path, model, *, hand_model=None, face_model=None):
    import mediapipe as mp

    command = [
        'ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-map', '0:v:0',
        '-t', '241', '-vf', f'fps={FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,'
        f'pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2', '-pix_fmt', 'rgb24', '-threads', '1',
        '-f', 'rawvideo', 'pipe:1']
    frame_bytes = HEIGHT * WIDTH * 3
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
    poses = []
    detail = []
    shifts = []
    previous_gray = None
    import cv2
    running_mode = mp.tasks.vision.RunningMode.VIDEO
    # Keep decoded pixels on disk so long recordings cannot exhaust RAM.
    with tempfile.TemporaryFile() as pixels:
        subprocess.run(command, stdout=pixels, stderr=subprocess.PIPE, check=True, timeout=90)
        count, remainder = divmod(pixels.tell(), frame_bytes)
        if remainder or not 0 < count <= FPS * 240:
            raise ValueError('provide a video of up to 240 seconds')
        pixels.seek(0)
        with ExitStack() as stack:
            detector = stack.enter_context(mp.tasks.vision.PoseLandmarker.create_from_options(options))
            hand = face = None
            if hand_model:
                hand = stack.enter_context(mp.tasks.vision.HandLandmarker.create_from_options(
                    mp.tasks.vision.HandLandmarkerOptions(
                        base_options=mp.tasks.BaseOptions(model_asset_path=str(hand_model)),
                        running_mode=running_mode, num_hands=2)))
            if face_model:
                face = stack.enter_context(mp.tasks.vision.FaceLandmarker.create_from_options(
                    mp.tasks.vision.FaceLandmarkerOptions(
                        base_options=mp.tasks.BaseOptions(model_asset_path=str(face_model)),
                        running_mode=running_mode, output_facial_transformation_matrixes=True)))
            for index in range(count):
                frame = np.frombuffer(pixels.read(frame_bytes), np.uint8).reshape(HEIGHT, WIDTH, 3)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                found = detector.detect_for_video(image, index * 1000 // FPS).pose_landmarks
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                if poses:
                    shift = background_shift(previous_gray, gray, poses[-1])
                    if shift is not None:
                        shifts.append(shift)
                previous_gray = gray
                poses.append(found[0] if found else None)
                if hand or face:
                    timestamp = index * 1000 // FPS
                    hands = hand.detect_for_video(image, timestamp).hand_landmarks if hand else []
                    face_result = face.detect_for_video(image, timestamp) if face else None
                    faces = face_result.face_landmarks if face_result else []
                    transforms = face_result.facial_transformation_matrixes if face_result else []
                    yaw = absolute_face_yaw(transforms[0]) if len(transforms) else None
                    near_face = None
                    if hands and faces:
                        eyes = np.array([(faces[0][i].x, faces[0][i].y) for i in (33, 263)])
                        nose = np.array([faces[0][1].x, faces[0][1].y])
                        eye_span = np.linalg.norm(eyes[0] - eyes[1])
                        if eye_span >= .01:
                            near_face = bool(any(np.linalg.norm(np.array([finger.x, finger.y]) - nose)
                                                 <= eye_span for points in hands
                                                 for finger in (points[i] for i in (4, 8, 12, 16, 20))))
                    detail.append({'time_s': timestamp / 1000, 'hands_detected': len(hands) if hand else None,
                                   'face_detected': bool(faces) if face else None,
                                   'absolute_face_yaw_degrees': yaw,
                                   'fingertip_near_face': near_face})
    camera_motion = ('unavailable' if len(shifts) < max(5, (count - 1) * .5)
                     else 'movement_detected' if np.percentile(shifts, 90) >= 3 else 'low_translation')
    features = observations(poses)
    if camera_motion != 'low_translation':
        for name in ('torso_sway', 'vertical_motion'):
            features[name] = {'status': 'insufficient_evidence', 'value': None}
    if hand_model and face_model:
        usable = [row['fingertip_near_face'] for row in detail if row['fingertip_near_face'] is not None]
        features['hand_near_face'] = {'status': 'insufficient_evidence', 'value': None}
        if len(usable) >= 5:
            intervals = proximity_intervals(detail)
            features['hand_near_face'] = {'status': 'experimental', 'value': round(sum(usable) / len(usable), 4),
                'method': 'fingertip proximity in image plane', 'valid_frames': len(usable),
                'intervals': intervals, 'observed_returns': observed_proximity_returns(detail, intervals)}
    return {'schema_version': 1, 'quality': {'frames': count,
            'pose_frames': sum(p is not None for p in poses), 'camera_motion': camera_motion,
            'camera_tracked_transitions': len(shifts)}, 'features': features, 'landmark_evidence': detail}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--pose-model', type=Path, required=True)
    parser.add_argument('--hand-model', type=Path)
    parser.add_argument('--face-model', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(analyze_video(args.video, args.pose_model, hand_model=args.hand_model, face_model=args.face_model), allow_nan=False))
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Video analysis failed: {type(exc).__name__}\n')

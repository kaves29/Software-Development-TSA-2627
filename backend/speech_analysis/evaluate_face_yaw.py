"""Compare head-turn detection methods on independently labeled AFLW2000 images."""

import argparse
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .video import HEIGHT, WIDTH, absolute_face_yaw, nose_ear_asymmetry

TURN_DEGREES = 25
PROXY_THRESHOLDS = (.10, .15, .20, .25, .30, .40, .50, .60)


def scores(rows, method, threshold):
    actual = [row['yaw_reference'] >= TURN_DEGREES for row in rows]
    values = [row[method] for row in rows]
    predicted = [value is not None and value >= threshold for value in values]
    tp = sum(a and b for a, b in zip(actual, predicted))
    positives, detections = sum(actual), sum(predicted)
    return {
        'matches': tp, 'predictions': detections, 'references': positives,
        'f1': 2 * tp / (positives + detections) if positives + detections else None,
        'precision': tp / detections if detections else None,
        'recall': tp / positives if positives else None,
        'coverage': sum(value is not None for value in values) / len(rows),
    }


def observations_from_archive(archive, face_model, pose_model):
    import cv2
    import mediapipe as mp
    from scipy.io import loadmat

    vision = mp.tasks.vision
    face_options = vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(face_model)),
        output_facial_transformation_matrixes=True)
    pose_options = vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(pose_model)))
    images = sorted(name for name in archive.namelist()
                    if Path(name).name.startswith('image') and name.endswith('.jpg'))
    if len(images) < 360:
        raise ValueError('expected at least 360 labeled AFLW2000 images')
    names = np.random.default_rng(20261127).permutation(images)[:360]
    with (vision.FaceLandmarker.create_from_options(face_options) as face,
          vision.PoseLandmarker.create_from_options(pose_options) as pose):
        rows = []
        for name in names:
            label = loadmat(BytesIO(archive.read(name[:-4] + '.mat')))
            reference = abs(float(np.degrees(label['Pose_Para'].ravel()[1])))
            raw = cv2.imdecode(np.frombuffer(archive.read(name), dtype=np.uint8), cv2.IMREAD_COLOR)
            if raw is None:
                raise ValueError(f'cannot decode {name}')
            height, width = raw.shape[:2]
            scale = min(WIDTH / width, HEIGHT / height)
            resized = cv2.cvtColor(cv2.resize(raw, (round(width * scale), round(height * scale))),
                                   cv2.COLOR_BGR2RGB)
            pixels = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
            top, left = (HEIGHT - resized.shape[0]) // 2, (WIDTH - resized.shape[1]) // 2
            pixels[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=pixels)
            transforms = face.detect(image).facial_transformation_matrixes
            poses = pose.detect(image).pose_landmarks
            yaw = absolute_face_yaw(transforms[0]) if len(transforms) else None
            proxy = None
            if poses and all(min(poses[0][i].visibility, poses[0][i].presence) >= .65
                             for i in (0, 7, 8, 11, 12)):
                nose, ear_l, ear_r, shoulder_l, shoulder_r = (
                    np.array([poses[0][i].x, poses[0][i].y]) for i in (0, 7, 8, 11, 12))
                if np.linalg.norm(shoulder_l - shoulder_r) >= .05:
                    proxy = nose_ear_asymmetry(nose, (ear_l, ear_r))
            rows.append({'yaw_reference': reference, 'matrix': yaw, 'proxy': proxy})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('face_model', type=Path)
    parser.add_argument('pose_model', type=Path)
    args = parser.parse_args()
    with ZipFile(args.archive) as archive:
        observations = observations_from_archive(archive, args.face_model, args.pose_model)
    development, comparison = observations[:120], observations[120:]
    threshold = max(PROXY_THRESHOLDS,
                    key=lambda x: scores(development, 'proxy', x)['f1'] or 0)
    print(json.dumps({
        'evaluation_images': len(comparison), 'reference_yaw_threshold': TURN_DEGREES,
        'proxy_threshold': threshold, 'proxy': scores(comparison, 'proxy', threshold),
        'face_matrix': scores(comparison, 'matrix', TURN_DEGREES),
    }, indent=2))


if __name__ == '__main__':
    main()

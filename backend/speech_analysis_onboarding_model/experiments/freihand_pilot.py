"""Experimental 2D hand-joint localization on fixed FreiHAND research images.

Images are cropped hands. This does not evaluate continuous video tracking.
FreiHAND permits research use only; its terms prohibit commercial use.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("hand_model", type=Path)
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--supplementary",
        action="store_true",
        help="Use the separate 40-image follow-up sample",
    )
    args = parser.parse_args()
    if not 0 <= args.confidence <= 1:
        parser.error("confidence must be in [0, 1]")
    manifest_name = (
        "freihand_followup_manifest.json"
        if args.supplementary
        else "freihand_pilot_manifest.json"
    )
    manifest = json.loads(Path(__file__).with_name(manifest_name).read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.download:
        from remotezip import RemoteZip

        url = "https://lmb.informatik.uni-freiburg.de/data/freihand/FreiHAND_pub_v2_eval.zip"
        with RemoteZip(url, timeout=60) as archive:
            for sample in manifest["ids"]:
                for extension, folder in (("jpg", "rgb"), ("json", "anno")):
                    filename = f"{sample}.{extension}"
                    target = args.directory / filename
                    if not target.exists():
                        payload = archive.read(f"evaluation/{folder}/{filename}")
                        if (
                            hashlib.sha256(payload).hexdigest()
                            != manifest["hashes"][filename]
                        ):
                            raise ValueError(f"checksum mismatch: {filename}")
                        target.write_bytes(payload)
    for name, expected in manifest["hashes"].items():
        if hashlib.sha256((args.directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"checksum mismatch: {name}")
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.hand_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=args.confidence,
        min_hand_presence_confidence=args.confidence,
    )
    correct = detected = total = in_frame = 0
    errors = []
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        for sample in manifest["ids"]:
            annotation = json.loads((args.directory / f"{sample}.json").read_text())
            image = cv2.imread(str(args.directory / f"{sample}.jpg"))
            height, width = image.shape[:2]
            xyz, camera = np.array(annotation["xyz"]), np.array(annotation["K"])
            projected = xyz @ camera.T
            uv = projected[:, :2] / projected[:, 2, None]
            diagonal = np.linalg.norm(np.ptp(uv, axis=0))
            if diagonal <= 0 or len(uv) != 21:
                raise ValueError(f"invalid projected hand: {sample}")
            in_frame += int(
                np.all(
                    (uv[:, 0] >= 0)
                    & (uv[:, 0] < width)
                    & (uv[:, 1] >= 0)
                    & (uv[:, 1] < height)
                )
            )
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            result = detector.detect(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            )
            total += 21
            if result.hand_landmarks:
                detected += 1
                prediction = np.array(
                    [[p.x * width, p.y * height] for p in result.hand_landmarks[0]]
                )
                error = np.linalg.norm(prediction - uv, axis=1) / diagonal
                correct += int((error <= 0.1).sum())
                errors.extend(error.tolist())
    print(
        json.dumps(
            {
                "samples": len(manifest["ids"]),
                "detections": detected,
                "joints": total,
                "within_0.1_diagonal": correct,
                "pck_including_missing": correct / total,
                "mean_error_detected": float(np.mean(errors)) if errors else None,
                "median_error_detected": float(np.median(errors)) if errors else None,
                "all_joints_in_frame": in_frame,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Probe camera-motion abstention using controlled crops of two AMI close-ups."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from speech_analysis_onboarding_model.video import analyze_video

CROPS = {
    "still": "crop=384:384:64:64",
    "horizontal": "crop=384:384:x='64+30*sin(2*PI*t/4)':y=64",
    "vertical": "crop=384:384:x=64:y='64+30*sin(2*PI*t/4)'",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_dir", type=Path)
    parser.add_argument("pose_model", type=Path)
    args = parser.parse_args()
    # Fixed development/training subjects; transformed clips are not independent subjects.
    samples = []
    with tempfile.TemporaryDirectory() as directory:
        for speaker in ("ES2008a.A", "IS1008a.D"):
            for kind, crop in CROPS.items():
                target = Path(directory) / f"{speaker}.{kind}.mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-nostdin",
                        "-y",
                        "-ss",
                        "40",
                        "-t",
                        "12",
                        "-i",
                        str(args.video_dir / f"{speaker}.avi"),
                        "-an",
                        "-vf",
                        "scale=512:512," + crop,
                        "-c:v",
                        "mpeg4",
                        "-q:v",
                        "5",
                        str(target),
                    ],
                    check=True,
                    timeout=120,
                )
                result = analyze_video(target, args.pose_model, max_seconds=13)
                samples.append(
                    {
                        "speaker": speaker,
                        "augmentation": kind,
                        "camera_motion": result["quality"]["camera_motion"],
                        "tracked_transitions": result["quality"][
                            "camera_tracked_transitions"
                        ],
                        "torso_sway": result["features"]["torso_sway"],
                    }
                )
                print(json.dumps(samples[-1]), flush=True)
    tp = fp = fn = tn = unavailable = 0
    for sample in samples:
        target = sample["augmentation"] != "still"
        status = sample["camera_motion"]
        if status == "unavailable":
            unavailable += 1
            if target:
                fn += 1
            else:
                fp += 1
        elif status == "movement_detected":
            if target:
                tp += 1
            else:
                fp += 1
        elif target:
            fn += 1
        else:
            tn += 1
    print(
        json.dumps(
            {
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
                "unavailable": unavailable,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

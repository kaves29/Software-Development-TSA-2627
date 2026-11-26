"""Extract only three training-speaker gesture tracks from the public GESRes CSVs."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ANNOTATION_SHA256 = "d78eac67bcb48eb36733117de56b79247d2092356cfec1369e8c6e4ad3879919"
POSE_SHA256 = "58ee21f3c68a18efcb809f2a2cce60377f3928c9047b123ccd218590dd4c42d2"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("pose_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--cohort", choices=("educators", "train5", "dev2"), default="educators"
    )
    args = parser.parse_args()
    if (
        digest(args.annotations) != ANNOTATION_SHA256
        or digest(args.pose_csv) != POSE_SHA256
    ):
        raise ValueError("input files do not match the recorded GESRes release")
    groups = {
        "educators": {"Lecturer1", "Lecturer2", "Lecturer3"},
        "train5": {"Lecturer1", "Lecturer2", "Lecturer3", "Politician1", "Clinician2"},
        "dev2": {"Politician2", "Clinician3"},
    }
    expected = {"educators": 767, "train5": 1254, "dev2": 747}
    with args.annotations.open(encoding="utf-8-sig", newline="") as stream:
        labels = {
            int(row["annotation_number"]): {
                "speaker": row["id_short"],
                "reps": row["reps"],
                "duration": row["duration"],
                "handedness": row["handedness"],
            }
            for row in csv.DictReader(stream)
            if row["id_short"] in groups[args.cohort]
        }
    if (
        len(labels) != expected[args.cohort]
        or {row["speaker"] for row in labels.values()} != groups[args.cohort]
    ):
        raise ValueError("unexpected identities or annotation count")
    columns = ["frame_index", "annotation_number"] + [
        f"point_{point}_{field}"
        for point in (11, 12, 13, 14, 15, 16)
        for field in ("x", "y", "z", "visibility", "presence")
    ]
    tracks = defaultdict(list)
    for chunk in pd.read_csv(args.pose_csv, usecols=columns, chunksize=50000):
        chunk = chunk[chunk.annotation_number.isin(labels)]
        for identity, part in chunk.groupby("annotation_number"):
            tracks[int(identity)].append(part[columns].to_numpy(dtype=np.float32))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output_dir / "educator_tracks.npz",
        **{str(key): np.concatenate(parts) for key, parts in tracks.items()},
    )
    (args.output_dir / "educator_labels.json").write_text(json.dumps(labels, indent=2))
    print("annotations", len(labels), "with_pose", len(tracks))


if __name__ == "__main__":
    main()

"""Exploratory gesture classification from a labeled, speaker-disjoint training subset."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

parser = argparse.ArgumentParser(
    description="Evaluate frozen gesture classifiers on separate development speakers."
)
parser.add_argument("directory", type=Path)
parser.add_argument("metadata", type=Path)
parser.add_argument(
    "--transfer",
    action="store_true",
    help="Evaluate on five TED speakers instead of Ecolang speakers",
)
parser.add_argument(
    "--more-training",
    action="store_true",
    help="Train on all ten Ecolang speakers for the transfer experiment",
)
parser.add_argument(
    "--domain-training",
    action="store_true",
    help="Add one separate TED training speaker to the transfer experiment",
)
args = parser.parse_args()
if args.more_training and not args.transfer:
    parser.error("--more-training requires --transfer")
if args.domain_training and not args.more_training:
    parser.error("--domain-training requires --more-training and --transfer")
root = args.directory
manifest_path = Path(__file__).with_name("gesture_pilot_manifest.json")
manifest = json.loads(manifest_path.read_text())
if hashlib.md5(args.metadata.read_bytes()).hexdigest() != manifest["metadata_md5"]:
    raise ValueError("metadata hash differs from the pilot manifest")
with args.metadata.open(newline="") as stream:
    approved = {
        (row["corpus"], row["speaker"])
        for row in csv.DictReader(stream)
        if row["set"] == "train"
    }
data = []
for sample in sorted(manifest["samples"], key=lambda item: Path(item["path"]).name):
    selected_role = (
        "transfer_development" if args.transfer else "prospective_development"
    )
    roles = {"training", selected_role}
    if args.more_training:
        roles.add("prospective_development")
    if args.domain_training:
        roles.add("domain_adaptation_training")
    if sample["role"] not in roles:
        continue
    path = root / Path(sample["path"]).name
    if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
        raise ValueError(f"sample hash differs from manifest: {path.name}")
    with np.load(path, allow_pickle=False) as z:
        body = z["world_body_landmarks"]
        speaker = str(z["speaker"])
        label = str(z["category"])
        fps = float(z["fps"])
        corpus = str(z["corpus"])
    if (corpus, speaker) not in approved:
        raise ValueError(f"non-training corpus speaker: {corpus}/{speaker}")
    if len(body) < 3 or label not in ("Gesture", "NoGesture"):
        continue
    xyz = body[:, :, :3]
    center = (xyz[:, 11, :] + xyz[:, 12, :]) / 2
    width = np.linalg.norm(xyz[:, 11, :] - xyz[:, 12, :], axis=1)
    valid = np.isfinite(center).all(axis=1) & np.isfinite(width) & (width > 0.01)
    positions = np.full((len(body), 4, 3), np.nan)
    positions[valid] = (
        xyz[valid][:, [13, 14, 15, 16], :] - center[valid, None, :]
    ) / width[valid, None, None]
    positions[~np.isfinite(positions)] = np.nan
    speed = np.linalg.norm(np.diff(positions, axis=0), axis=2) * fps
    features = []
    for values in (positions[:, :, 0], positions[:, :, 1], positions[:, :, 2], speed):
        for col in range(4):
            v = values[:, col]
            v = v[np.isfinite(v)]
            features.extend(
                np.quantile(v, [0.1, 0.5, 0.9]).tolist()
                if len(v) > 0
                else [0.0, 0.0, 0.0]
            )
    features.extend([float(valid.mean()), float(np.isfinite(positions).mean())])
    data.append(
        (
            speaker,
            label == "Gesture",
            features,
            path.name,
            float(np.isfinite(positions).mean()),
            float(np.nanmean(np.any(speed[:, 2:4] >= 2, axis=1))),
        )
    )

# Frozen prospective evaluation: first five speakers used for development;
# the second five were not inspected when choosing these two methods.
training_speakers = {"ad03", "ad05", "ad07", "ad09", "ad10"}
if args.more_training:
    training_speakers |= {"ad11", "ad14", "ad15", "ad16", "ad19"}
if args.domain_training:
    training_speakers.add("M3D_TED_SJ2010")
evaluation_speakers = {"ad11", "ad14", "ad15", "ad16", "ad19"}
if args.transfer:
    evaluation_speakers = {
        "M3D_TED_DL2016",
        "M3D_TED_EG2009",
        "M3D_TED_ES2016",
        "M3D_TED_FB2015",
        "M3D_TED_MD2018",
    }
train = [r for r in data if r[0] in training_speakers]
test = [r for r in data if r[0] in evaluation_speakers]
expected_training = 360 if args.domain_training else 300 if args.more_training else 150
if len(train) != expected_training or len(test) != 150:
    raise ValueError(
        f"expected {expected_training} training and 150 evaluation examples, got {len(train)} and {len(test)}"
    )
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=6,
    min_samples_leaf=4,
    class_weight="balanced",
    random_state=42,
    n_jobs=2,
)
model.fit([r[2] for r in train], [r[1] for r in train])
y = np.asarray([r[1] for r in test])
methods = {
    "forest": model.predict([r[2] for r in test]),
    "rapid_motion": np.asarray([r[5] >= 0.2 for r in test]),
    "always_positive": np.ones(len(test), dtype=bool),
}
for name, pred in methods.items():
    for speaker in ["pooled"] + sorted(evaluation_speakers):
        mask = np.asarray([speaker == "pooled" or r[0] == speaker for r in test])
        matrix = confusion_matrix(y[mask], pred[mask], labels=[False, True])
        p, r, f, _ = precision_recall_fscore_support(
            y[mask], pred[mask], average="binary", zero_division=0
        )
        print(
            name,
            speaker,
            "P/R/F1",
            round(p, 4),
            round(r, 4),
            round(f, 4),
            "confusion",
            matrix.tolist(),
            flush=True,
        )

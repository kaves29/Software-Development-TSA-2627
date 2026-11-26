"""Frozen cross-corpus gesture development check, not full-video validation."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
)
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
parser.add_argument("--additional-speakers", action="store_true")
args = parser.parse_args()
root = args.directory
manifest = json.loads(
    Path(__file__).with_name("gesture_pilot_manifest.json").read_text()
)
expanded = [
    e["path"]
    for e in json.loads(
        Path(__file__).with_name("gesture_domain_manifest.json").read_text()
    )["samples"]
]
train_names = {
    Path(e["path"]).name
    for e in manifest["samples"]
    if e["role"]
    in ("training", "prospective_development", "domain_adaptation_training")
}
for n in expanded:
    if any("_" + s + "_" in Path(n).name for s in ("M3D_TED_DL2016", "M3D_TED_EG2009")):
        train_names.add(Path(n).name)
targets = ["P010_S04", "P012_S05"]
test_names = {
    Path(n).name
    for n in [
        e["path"]
        for e in json.loads(
            Path(__file__).with_name("gesture_multisimo_manifest.json").read_text()
        )["samples"]
    ]
}
if args.additional_speakers:
    targets += ["P016_S07", "P019_S08", "P020_S09", "P023_S10"]
    test_names |= {
        Path(sample["path"]).name
        for sample in json.loads(
            Path(__file__)
            .with_name("gesture_multisimo_extra_manifest.json")
            .read_text()
        )["samples"]
    }
assert (
    len(train_names) == 560
    and len(test_names) == (180 if args.additional_speakers else 60)
    and not train_names & test_names
)


def quant(v):
    v = v[np.isfinite(v)]
    return np.quantile(v, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist() if len(v) else [0.0] * 5


def extract(name):
    with np.load(root / name, allow_pickle=False) as z:
        world = z["world_body_landmarks"]
        image = z["image_body_landmarks"]
        fps = float(z["fps"])
        speaker = str(z["speaker"])
        corpus = str(z["corpus"])
        label = str(z["category"]) == "Gesture"
    features = []
    for raw, dims in ((world, 3), (image, 2)):
        xyz = raw[:, :, :dims]
        center = (xyz[:, 11] + xyz[:, 12]) / 2
        width = np.linalg.norm(xyz[:, 11] - xyz[:, 12], axis=1)
        width[width < 0.01] = np.nan
        pos = (xyz[:, [13, 14, 15, 16]] - center[:, None, :]) / width[:, None, None]
        pos[~np.isfinite(pos)] = np.nan
        for j in range(4):
            for d in range(dims):
                features += quant(pos[:, j, d])
            for sigma in [0, 1, 3]:
                # Weighted smoothing avoids interpreting missing poses as coordinates.
                weight = np.isfinite(pos[:, j, :]).all(axis=1).astype(float)
                if sigma:
                    valid_weight = gaussian_filter1d(weight, sigma)
                    smooth = gaussian_filter1d(
                        np.nan_to_num(pos[:, j, :]), sigma, axis=0
                    ) / np.maximum(valid_weight[:, None], 1e-6)
                    smooth[valid_weight < 0.8] = np.nan
                else:
                    smooth = pos[:, j, :]
                diff = np.diff(smooth, axis=0)
                speed = np.linalg.norm(diff, axis=1) * fps
                features += quant(speed)
                features.extend(
                    [
                        float(np.isfinite(speed).mean()),
                        float(np.mean(speed > 1)),
                        float(np.mean(speed > 2)),
                        float(np.mean(speed > 4)),
                    ]
                )
                if sigma == 1:
                    accel = np.abs(np.diff(speed)) * fps
                    features += quant(accel)
                    if len(diff) > 1:
                        dot = np.sum(diff[:-1] * diff[1:], axis=1)
                        mag = np.linalg.norm(diff[:-1], axis=1) * np.linalg.norm(
                            diff[1:], axis=1
                        )
                        features += quant(dot / np.maximum(mag, 1e-8))
        features.extend(
            [float(np.isfinite(pos).mean()), float(np.isfinite(width).mean())]
        )
    return speaker, corpus, label, np.nan_to_num(features, nan=0, posinf=0, neginf=0)


checks = {}
sources = [
    "gesture_pilot_manifest.json",
    "gesture_domain_manifest.json",
    "gesture_multisimo_manifest.json",
]
if args.additional_speakers:
    sources.append("gesture_multisimo_extra_manifest.json")
for source in sources:
    for e in json.loads(Path(__file__).with_name(source).read_text())["samples"]:
        name = Path(e["path"]).name
        if name in checks and checks[name] != e["sha256"]:
            raise ValueError(f"conflicting hash {name}")
        checks[name] = e["sha256"]
for name in train_names | test_names:
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != checks[name]:
        raise ValueError(f"checksum mismatch: {name}")
D = {name: extract(name) for name in sorted(train_names | test_names)}
T = [D[n] for n in sorted(test_names)]
y = np.array([r[2] for r in T])
groups = np.array([r[0] for r in T])
tx = np.array([r[3] for r in T])
print("feature_size", tx.shape, flush=True)

train = [D[n] for n in sorted(train_names) if D[n][1] == "TedM3D"]
X = np.array([r[3] for r in train])
labels = np.array([r[2] for r in train])
print("training", len(train), flush=True)
model = HistGradientBoostingClassifier(
    max_iter=100, max_leaf_nodes=7, l2_regularization=1, random_state=42
)
model.fit(X, labels)
pred = model.predict_proba(tx)[:, 1] >= 0.35
for who in ["pooled"] + targets:
    mask = np.array([who == "pooled" or g == who for g in groups])
    p, r, f, _ = precision_recall_fscore_support(
        y[mask], pred[mask], average="binary", zero_division=0
    )
    print(
        "boost_fixed",
        who,
        "P/R/F1",
        round(p, 4),
        round(r, 4),
        round(f, 4),
        "matrix",
        confusion_matrix(y[mask], pred[mask], labels=[False, True]).tolist(),
        flush=True,
    )

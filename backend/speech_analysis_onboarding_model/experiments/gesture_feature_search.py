import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

parser = argparse.ArgumentParser(
    description="Exploratory grouped cross-validation on the pilot training speakers."
)
parser.add_argument("directory", type=Path)
root = parser.parse_args().directory
manifest = json.loads(
    Path(__file__).with_name("gesture_pilot_manifest.json").read_text()
)
expected = {
    Path(x["path"]).name: x["sha256"]
    for x in manifest["samples"]
    if x["role"] == "training"
}
speakers = ["ad03", "ad05", "ad07", "ad09", "ad10"]


def quant(x):
    x = np.asarray(x).ravel()
    x = x[np.isfinite(x)]
    return list(np.quantile(x, [0.1, 0.25, 0.5, 0.75, 0.9])) if len(x) else [0.0] * 5


def extract(path):
    with np.load(path, allow_pickle=False) as z:
        body = z["world_body_landmarks"][:, :, :3]
        fps = float(z["fps"])
        speaker = str(z["speaker"])
        label = str(z["category"]) == "Gesture"
        lh = z["world_left_hand_landmarks"][:, :, :3]
        rh = z["world_right_hand_landmarks"][:, :, :3]
    center = (body[:, 11] + body[:, 12]) / 2
    width = np.linalg.norm(body[:, 11] - body[:, 12], axis=1)
    width[width < 0.01] = np.nan
    pos = (body[:, [13, 14, 15, 16]] - center[:, None, :]) / width[:, None, None]
    pos[~np.isfinite(pos)] = np.nan
    feat = []
    for j in range(4):
        for k in range(3):
            feat += quant(pos[:, j, k])
        for sigma in [0, 2, 5]:
            # Missing values remain missing; do not interpolate across occlusions.
            t = (
                pos[:, j, :]
                if not sigma
                else gaussian_filter1d(pos[:, j, :], sigma, axis=0)
            )
            speed = np.linalg.norm(np.diff(t, axis=0), axis=1) * fps
            feat += quant(speed)
            feat += [
                np.mean(np.isfinite(speed)),
                np.mean(speed > 1),
                np.mean(speed > 2),
                np.mean(speed > 4),
            ]
    for h in [lh, rh]:
        span = np.linalg.norm(h[:, 5] - h[:, 17], axis=1)
        span[span < 0.001] = np.nan
        for tip in [4, 8, 12, 16, 20]:
            feat += quant(np.linalg.norm(h[:, tip] - h[:, 0], axis=1) / span)
        for a, b in [(4, 8), (8, 12), (12, 16), (16, 20)]:
            feat += quant(np.linalg.norm(h[:, a] - h[:, b], axis=1) / span)
        feat += [float(np.isfinite(h).mean())]
    feat = np.nan_to_num(feat, nan=0, posinf=0, neginf=0)
    return speaker, label, feat


D = []
for name, checksum in sorted(expected.items()):
    p = root / name
    if hashlib.sha256(p.read_bytes()).hexdigest() != checksum:
        raise ValueError(f"sample hash differs from manifest: {name}")
    D.append(extract(p))
print("data", len(D), len(D[0][2]), flush=True)
X = np.array([r[2] for r in D])
y = np.array([r[1] for r in D])
groups = np.array([r[0] for r in D])
models = {
    "forest_shallow": RandomForestClassifier(
        n_estimators=250,
        max_depth=5,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=2,
    ),
    "forest_deeper": RandomForestClassifier(
        n_estimators=250,
        max_depth=10,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=2,
    ),
    "extra": ExtraTreesClassifier(
        n_estimators=250,
        max_depth=8,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=2,
    ),
    "logistic": make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.01, class_weight="balanced", max_iter=2000),
    ),
    "boost": HistGradientBoostingClassifier(
        max_iter=100, max_leaf_nodes=7, l2_regularization=1, random_state=42
    ),
}
for name, m in models.items():
    for feature_slice in [slice(None, 168), slice(168, None), slice(None)]:
        predictions = np.zeros(len(D), dtype=bool)
        for s in speakers:
            train = groups != s
            test = groups == s
            m.fit(X[train, feature_slice], y[train])
            predictions[test] = m.predict(X[test, feature_slice])
        print(
            name,
            str(feature_slice),
            round(f1_score(y, predictions), 4),
            confusion_matrix(y, predictions).tolist(),
            flush=True,
        )

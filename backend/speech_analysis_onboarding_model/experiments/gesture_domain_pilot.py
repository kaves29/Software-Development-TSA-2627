"""Exploratory speaker-disjoint gesture classification, not final validation."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
root = parser.parse_args().directory
manifest = json.loads(
    Path(__file__).with_name("gesture_pilot_manifest.json").read_text()
)
expanded = [
    x["path"]
    for x in json.loads(
        Path(__file__).with_name("gesture_domain_manifest.json").read_text()
    )["samples"]
]
files = {
    Path(e["path"]).name
    for e in manifest["samples"]
    if e["role"]
    in ("training", "prospective_development", "domain_adaptation_training")
}
# Fix the already inspected TED evaluation split; no test speaker contributes training clips.
test_speakers = ["M3D_TED_ES2016", "M3D_TED_FB2015", "M3D_TED_MD2018"]
test = {
    Path(e["path"]).name
    for e in manifest["samples"]
    if e["role"] == "transfer_development"
    and any("_" + s + "_" in Path(e["path"]).name for s in test_speakers)
}
for n in expanded:
    if any("_" + s + "_" in Path(n).name for s in ["M3D_TED_DL2016", "M3D_TED_EG2009"]):
        files.add(Path(n).name)
assert len(test) == 90 and len(files) == 560 and not files & test, (
    len(test),
    len(files),
)


def extract(path):
    with np.load(path, allow_pickle=False) as z:
        body = z["world_body_landmarks"]
        speaker = str(z["speaker"])
        label = str(z["category"]) == "Gesture"
        fps = float(z["fps"])
        corpus = str(z["corpus"])
    xyz = body[:, :, :3]
    center = (xyz[:, 11, :] + xyz[:, 12, :]) / 2
    width = np.linalg.norm(xyz[:, 11, :] - xyz[:, 12, :], axis=1)
    valid = np.isfinite(center).all(axis=1) & np.isfinite(width) & (width > 0.01)
    pos = np.full((len(body), 4, 3), np.nan)
    pos[valid] = (xyz[valid][:, [13, 14, 15, 16], :] - center[valid, None, :]) / width[
        valid, None, None
    ]
    pos[~np.isfinite(pos)] = np.nan
    speed = np.linalg.norm(np.diff(pos, axis=0), axis=2) * fps
    feat = []
    for values in (pos[:, :, 0], pos[:, :, 1], pos[:, :, 2], speed):
        for col in range(4):
            v = values[:, col]
            v = v[np.isfinite(v)]
            feat.extend(
                np.quantile(v, [0.1, 0.5, 0.9]).tolist() if len(v) else [0.0, 0.0, 0.0]
            )
    feat.extend([float(valid.mean()), float(np.isfinite(pos).mean())])
    return speaker, corpus, label, feat


checks = {Path(e["path"]).name: e["sha256"] for e in manifest["samples"]}
for e in json.loads(
    Path(__file__).with_name("gesture_domain_manifest.json").read_text()
)["samples"]:
    name = Path(e["path"]).name
    if name in checks and checks[name] != e["sha256"]:
        raise ValueError(f"conflicting hash {name}")
    checks[name] = e["sha256"]
for name in files | test:
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != checks[name]:
        raise ValueError(f"sample checksum mismatch: {name}")
D = {n: extract(root / n) for n in sorted(files | test)}
T = [D[n] for n in sorted(test)]
truth = np.array([r[2] for r in T])
groups = np.array([r[0] for r in T])
tx = np.array([r[3] for r in T])
for mode in ("eco", "eco_sj", "all", "target_only"):
    tr = [
        D[n]
        for n in sorted(files)
        if mode == "all"
        or (mode == "eco" and D[n][1] == "Ecolang")
        or (mode == "eco_sj" and (D[n][1] == "Ecolang" or D[n][0] == "M3D_TED_SJ2010"))
        or (mode == "target_only" and D[n][1] == "TedM3D")
    ]
    X = np.array([r[3] for r in tr])
    y = np.array([r[2] for r in tr])
    print("train", mode, len(y), int(y.sum()), flush=True)
    for kind in ("forest", "extra", "logistic"):
        model = {
            "forest": RandomForestClassifier(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=4,
                class_weight="balanced",
                random_state=42,
                n_jobs=2,
            ),
            "extra": ExtraTreesClassifier(
                n_estimators=200,
                max_depth=8,
                min_samples_leaf=4,
                class_weight="balanced",
                random_state=42,
                n_jobs=2,
            ),
            "logistic": make_pipeline(
                StandardScaler(),
                LogisticRegression(C=0.1, class_weight="balanced", max_iter=1000),
            ),
        }[kind]
        model.fit(X, y)
        prob = model.predict_proba(tx)[:, 1]
        for cut in (0.35, 0.5, 0.65):
            pred = prob >= cut
            p, r, f, _ = precision_recall_fscore_support(
                truth, pred, average="binary", zero_division=0
            )
            print(
                mode,
                kind,
                cut,
                "P/R/F1",
                round(p, 3),
                round(r, 3),
                round(f, 3),
                "matrix",
                confusion_matrix(truth, pred).tolist(),
                "folds",
                [
                    (
                        s,
                        round(
                            precision_recall_fscore_support(
                                truth[groups == s],
                                pred[groups == s],
                                average="binary",
                                zero_division=0,
                            )[2],
                            3,
                        ),
                    )
                    for s in test_speakers
                ],
                flush=True,
            )

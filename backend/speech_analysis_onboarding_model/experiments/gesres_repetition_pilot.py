"""Explore repetition detection on presegmented training-speaker gestures."""

import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("data_dir", type=Path)
root = parser.parse_args().data_dir
labels = json.loads((root / "educator_labels.json").read_text())
tracks = np.load(root / "educator_tracks.npz", allow_pickle=False)
grid = list(product([1, 2, 4], [0.08, 0.15, 0.25, 0.4], [2, 3, 4, 5]))
rows = []
for k, v in sorted(labels.items(), key=lambda x: int(x[0])):
    q = tracks[k]
    q = q[np.argsort(q[:, 0])]
    p = q[:, 2:].reshape(-1, 6, 5).astype(float)
    center = (p[:, 0, :2] + p[:, 1, :2]) / 2
    scale = np.linalg.norm(p[:, 0, :2] - p[:, 1, :2], axis=1)
    valid = (
        np.isfinite(center).all(axis=1)
        & np.isfinite(scale)
        & (scale > 0.02)
        & (p[:, 0, 3] > 0.65)
        & (p[:, 1, 3] > 0.65)
    )
    curves = []
    for j in range(2):
        ok = valid & np.isfinite(p[:, 4 + j, :2]).all(axis=1) & (p[:, 4 + j, 3] > 0.65)
        for axis in range(2):
            y = np.full(len(p), np.nan)
            y[ok] = (p[ok, 4 + j, axis] - center[ok, axis]) / scale[ok]
            idx = np.where(np.isfinite(y))[0]
            if len(idx) >= 6:
                curves.append(np.interp(np.arange(len(y)), idx, y[idx]))
    label = int(v["reps"].split()[0]) >= 2
    result = {}
    for smooth, prom in product([1, 2, 4], [0.08, 0.15, 0.25, 0.4]):
        if not curves:
            score = None
        else:
            score = max(
                len(
                    find_peaks(
                        gaussian_filter1d(y, smooth), prominence=prom, distance=3
                    )[0]
                )
                + len(
                    find_peaks(
                        -gaussian_filter1d(y, smooth), prominence=prom, distance=3
                    )[0]
                )
                for y in curves
            )
        result[(smooth, prom)] = score
    rows.append((k, v["speaker"], label, result))


def evaluate(sub, setting):
    sigma, prom, cut = setting
    tn = fp = fn = tp = 0
    for _, _, label, res in sub:
        score = res[(sigma, prom)]
        if score is None:
            # Count abstentions against the correct class for conservative assessment.
            if label:
                fn += 1
            else:
                fp += 1
        elif score >= cut:
            if label:
                tp += 1
            else:
                fp += 1
        elif label:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0
    return precision, recall, f, [[tn, fp], [fn, tp]]


for speaker in sorted({r[1] for r in rows}):
    train = [r for r in rows if r[1] != speaker]
    test = [r for r in rows if r[1] == speaker]
    best = max(grid, key=lambda x: (evaluate(train, x)[2], x))
    print(
        speaker,
        "selected",
        best,
        "train",
        evaluate(train, best),
        "test",
        evaluate(test, best),
        flush=True,
    )

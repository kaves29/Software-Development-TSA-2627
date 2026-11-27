"""Explore repetition detection on presegmented training-speaker gestures."""

import argparse
import json
from itertools import pairwise, product
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import correlate, find_peaks

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("data_dir", type=Path)
parser.add_argument(
    "--fixed",
    action="store_true",
    help="Evaluate the fixed five-speaker development rule",
)
parser.add_argument(
    "--cycle-consistency",
    action="store_true",
    help="Require repeated extrema of the same polarity at comparable amplitudes",
)
parser.add_argument("--autocorrelation", action="store_true")
args = parser.parse_args()
if args.fixed and (args.cycle_consistency or args.autocorrelation):
    parser.error("the fixed baseline uses the original extrema count")
root = args.data_dir
labels = json.loads((root / "educator_labels.json").read_text())
tracks = np.load(root / "educator_tracks.npz", allow_pickle=False)
grid = list(product([1, 2, 4], [0.08, 0.15, 0.25, 0.4], [2, 3, 4, 5]))
if args.autocorrelation:
    grid = list(product([1, 2, 4], [0.08, 0.15, 0.25, 0.4], [0.4, 0.55, 0.7, 0.85]))
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
        counts = []
        for curve in curves:
            smoothed = gaussian_filter1d(curve, smooth)
            if args.autocorrelation:
                # A repeated trajectory should resemble itself after a nontrivial lag.
                centered = smoothed - np.linspace(smoothed[0], smoothed[-1], len(smoothed))
                if np.ptp(centered) < prom:
                    counts.append(0.0)
                    continue
                size = len(centered)
                lags = np.arange(4, size // 2 + 1)
                count = size - lags
                sums = np.r_[0, np.cumsum(centered)]
                squared = np.r_[0, np.cumsum(centered ** 2)]
                left_sum, right_sum = sums[count], sums[-1] - sums[lags]
                left_var = squared[count] - left_sum ** 2 / count
                right_var = squared[-1] - squared[lags] - right_sum ** 2 / count
                covariance = correlate(centered, centered)[size - 1 + lags]
                covariance -= left_sum * right_sum / count
                norm = np.sqrt(np.maximum(left_var, 0) * np.maximum(right_var, 0))
                correlation = np.divide(covariance, norm, out=np.zeros_like(norm), where=norm > 0)
                peaks_in_lag = find_peaks(correlation)[0]
                counts.append(max((correlation[i] for i in peaks_in_lag), default=0.0))
                continue
            peaks = [find_peaks(sign * smoothed, prominence=prom, distance=3)[0]
                     for sign in (1, -1)]
            if not args.cycle_consistency:
                counts.append(sum(len(indices) for indices in peaks))
                continue
            # A similar return position helps reject large one-off sweeps.
            counts.append(max(
                (1 + sum(abs(smoothed[right] - smoothed[left]) <= prom
                         for left, right in pairwise(indices))
                 for indices in peaks if len(indices)),
                default=0,
            ))
        result[(smooth, prom)] = max(counts, default=None)
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


if args.fixed:
    setting = (2, 0.08, 3)
    for speaker in sorted({r[1] for r in rows}):
        group = [r for r in rows if r[1] == speaker]
        print(
            speaker,
            "available",
            sum(r[3][(2, 0.08)] is not None for r in group),
            "total",
            len(group),
            "test",
            evaluate(group, setting),
            flush=True,
        )
    print("pooled", evaluate(rows, setting), flush=True)
else:
    held_out = []
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
        held_out.append(evaluate(test, best)[3])
    pooled = np.sum(held_out, axis=0)
    (_, fp), (fn, tp) = pooled
    print("pooled", float(2 * tp / max(1, 2 * tp + fp + fn)), pooled.tolist())

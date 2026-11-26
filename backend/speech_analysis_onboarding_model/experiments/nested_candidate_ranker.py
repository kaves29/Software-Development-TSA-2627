"""Nested grouped development evaluation of combined filler candidates."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import (
    ExtraTreesClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference
from speech_analysis_onboarding_model.filler_frames import decode_frames

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--annotations", type=Path, required=True)
parser.add_argument("--sdk-dir", type=Path, required=True)
parser.add_argument("--acoustic-dir", type=Path, required=True)
parser.add_argument("--label-dir", type=Path, required=True)
parser.add_argument("--holdout", help="Evaluate one specified recording as the outer fold")
parser.add_argument("recordings", nargs="+")
args = parser.parse_args()
names = args.recordings
if args.holdout and args.holdout not in names:
    parser.error("holdout must be one of the supplied recordings")
if len(set(names)) != len(names) or len(names) < 4:
    parser.error("provide at least four unique recordings")
with ZipFile(args.annotations) as z:
    splits = recording_splits(z)
    permitted = {
        row["recording"]: row["speaker"]
        for split in ("training", "development")
        for row in splits[split]
    }
if not set(names) <= permitted.keys() or len({permitted[n] for n in names}) != len(
    names
):
    parser.error(
        "recordings must be official training or development and have distinct speakers"
    )
data = {}
for n in names:
    a = json.loads((args.sdk_dir / f"{n}.recall.json").read_text())
    w = np.load(args.label_dir / f"{n}.frame.npy", allow_pickle=False)
    p = np.load(args.acoustic_dir / f"{n}.npy", allow_pickle=False)[:, 0]
    with ZipFile(args.annotations) as z:
        refs = filler_reference(z, n, a["duration"])
    acoustic = decode_frames(
        np.column_stack((1 - p, p, np.zeros_like(p))), a["duration"], 0.5, 6
    )
    used = set()
    candidates = []
    for u in a["fillers"]:
        mid = (u["start"] + u["end"]) / 2
        eligible = [
            (abs(mid - (e["start_s"] + e["end_s"]) / 2), i)
            for i, e in enumerate(acoustic)
            if i not in used
        ]
        dist, idx = min(eligible, default=(100, None))
        found = dist <= 0.25
        if found:
            used.add(idx)
        candidates.append(
            (
                u["start"],
                u["end"],
                u["confidence"],
                acoustic[idx]["score"] if found else 0,
                int(found),
                1,
            )
        )
    for i, e in enumerate(acoustic):
        if i not in used:
            candidates.append((e["start_s"], e["end_s"], 0, e["score"], 0, 0))
    events = []
    X = []
    for start, end, conf, ac_score, both, is_sdk in candidates:
        i = max(0, int(start / 0.02))
        j = min(len(w), len(p), max(i + 1, round(end / 0.02)))
        pp = p[i:j]
        ww = w[i:j]
        if not len(pp):
            continue
        probs = ww[:, 1:3].mean(0)
        events.append(
            {"start_s": start, "end_s": end, "text": ["um", "uh"][probs.argmax()]}
        )
        X.append(
            [
                conf,
                end - start,
                *probs,
                pp.mean(),
                pp.max(),
                np.quantile(pp, 0.25),
                np.quantile(pp, 0.75),
                ac_score,
                both,
                is_sdk,
            ]
        )
    X = np.array(X)
    cost = np.ones((len(events), len(refs))) * 1000
    for i, e in enumerate(events):
        for j, r in enumerate(refs):
            err1 = abs(e["start_s"] - r["start_s"])
            err2 = abs(e["end_s"] - r["end_s"])
            if max(err1, err2) <= 0.25:
                cost[i, j] = err1 + err2
    ii, jj = linear_sum_assignment(cost)
    match = {i: j for i, j in zip(ii, jj) if cost[i, j] < 1000}
    y = np.array(
        [
            {"um": 1, "uh": 2}[refs[match[i]]["text"]] if i in match else 0
            for i in range(len(events))
        ]
    )
    data[n] = (a["duration"], events, refs, X, y)
    print("counts", n, len(events), len(refs), len(match), flush=True)

from itertools import product

thresholds = (0.15, 0.3, 0.45, 0.6)
keys = list(product(thresholds, ("wavlm", "learned")))


def infer(train, target):
    X = np.concatenate([data[n][3] for n in train])
    y = np.concatenate([data[n][4] for n in train])
    d, events, refs, tx, _ = data[target]
    m = ExtraTreesClassifier(
        n_estimators=150,
        max_depth=5,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=2,
    ).fit(X, y > 0)
    c = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000),
    ).fit(X[y > 0], y[y > 0])
    p = m.predict_proba(tx)[:, 1]
    typed = c.predict(tx)
    result = {}
    for cut, method in keys:
        out = [
            {**e, "text": e["text"] if method == "wavlm" else {1: "um", 2: "uh"}[t]}
            for e, t, v in zip(events, typed, p)
            if v >= cut
        ]
        result[(cut, method)] = {"duration_s": d, "predicted": out, "reference": refs}
    return result


rows = []
for outer in ([args.holdout] if args.holdout else names):
    train = [n for n in names if n != outer]
    inner = {k: [] for k in keys}
    for val in train:
        choices = infer([n for n in train if n != val], val)
        for k, v in choices.items():
            inner[k].append(v)
    best = max(keys, key=lambda k: (recording_event_metrics(inner[k])["f1"], k[0]))
    row = infer(train, outer)[best]
    rows.append(row)
    print(
        "outer",
        outer,
        "selected",
        best,
        "inner_f1",
        round(recording_event_metrics(inner[best])["f1"], 4),
        "outer_f1",
        round(recording_event_metrics([row])["f1"], 4),
        flush=True,
    )
print("nested_pooled", recording_event_metrics(rows), flush=True)

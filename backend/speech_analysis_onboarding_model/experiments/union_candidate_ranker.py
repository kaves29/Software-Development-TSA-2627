"""Exploratory grouped AMI candidate model; never use for final test scoring."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import (
    ExtraTreesClassifier,
    RandomForestClassifier,
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
parser.add_argument("recordings", nargs="+")
args = parser.parse_args()
names = args.recordings
if len(set(names)) != len(names) or len(names) < 3:
    parser.error("provide at least three unique recordings")
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
rows = {}
for target in names:
    train = [n for n in names if n != target]
    X = np.concatenate([data[n][3] for n in train])
    y = np.concatenate([data[n][4] for n in train])
    d, e, refs, tx, ty = data[target]
    class_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000),
    )
    class_model.fit(X[y > 0], y[y > 0])
    types = class_model.predict(tx)
    models = {
        "forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=4,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=2,
        ),
        "extra": ExtraTreesClassifier(
            n_estimators=300,
            max_depth=5,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=2,
        ),
        "logistic": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000),
        ),
    }
    for name, model in models.items():
        model.fit(X, y > 0)
        probs = model.predict_proba(tx)[:, 1]
        for cut in (0.3, 0.5, 0.7):
            for typ in ("wavlm", "learned"):
                pred = [
                    {
                        **event,
                        "text": event["text"]
                        if typ == "wavlm"
                        else {1: "um", 2: "uh"}[t],
                    }
                    for event, t, k in zip(e, types, probs)
                    if k >= cut
                ]
                rows.setdefault((name, cut, typ), []).append(
                    {"duration_s": d, "predicted": pred, "reference": refs}
                )
for key, rs in rows.items():
    m = recording_event_metrics(rs)
    print(
        key,
        "m/p/r/f1",
        m["matches"],
        m["predictions"],
        m["references"],
        round(m["f1"], 4),
        "folds",
        [(n, round(recording_event_metrics([r])["f1"], 3)) for n, r in zip(names, rs)],
        flush=True,
    )

"""Exploratory grouped AMI candidate model; never use for final test scoring."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference

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
    events = []
    X = []
    for u in a["fillers"]:
        i = max(0, int(u["start"] / 0.02))
        j = min(len(w), len(p), max(i + 1, round(u["end"] / 0.02)))
        pp = p[i:j]
        ww = w[i:j]
        if not len(pp):
            continue
        probs = ww[:, 1:3].mean(0)
        label = ["um", "uh"][probs.argmax()]
        events.append({"start_s": u["start"], "end_s": u["end"], "text": label})
        X.append(
            [
                u["confidence"],
                u["end"] - u["start"],
                *probs,
                pp.mean(),
                pp.max(),
                np.quantile(pp, 0.25),
                np.quantile(pp, 0.75),
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
    # 0 false, 1 um, 2 uh. Matching is untyped so type model can correct labeling.
    y = np.array(
        [
            {"um": 1, "uh": 2}[refs[match[i]]["text"]] if i in match else 0
            for i in range(len(events))
        ]
    )
    data[n] = (a["duration"], events, refs, X, y)
    print(
        "counts",
        n,
        "events",
        len(events),
        "references",
        len(refs),
        "matched",
        len(match),
        "um",
        sum(y == 1),
        "uh",
        sum(y == 2),
        flush=True,
    )
rows = {}
for target in names:
    train = [n for n in names if n != target]
    X = np.concatenate([data[n][3] for n in train])
    y = np.concatenate([data[n][4] for n in train])
    d, e, refs, tx, ty = data[target]
    models = {
        "forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=4,
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
        keep = model.predict_proba(tx)[:, 1]
        for cut in (0.3, 0.5):
            for type_method in ("wavlm", "learned"):
                yy = y > 0
                classifier = make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000),
                )
                classifier.fit(X[yy], y[yy])
                out = []
                for event, pred_type, k in zip(e, classifier.predict(tx), keep):
                    if k >= cut:
                        out.append(
                            {
                                **event,
                                "text": event["text"]
                                if type_method == "wavlm"
                                else {1: "um", 2: "uh"}[pred_type],
                            }
                        )
                rows.setdefault((name, cut, type_method), []).append(
                    {"duration_s": d, "predicted": out, "reference": refs}
                )
    rows.setdefault(("baseline", 0, "wavlm"), []).append(
        {"duration_s": d, "predicted": e, "reference": refs}
    )
for key, rs in rows.items():
    print(
        key,
        "pooled",
        recording_event_metrics(rs),
        "folds",
        [(n, round(recording_event_metrics([r])["f1"], 3)) for n, r in zip(names, rs)],
        flush=True,
    )

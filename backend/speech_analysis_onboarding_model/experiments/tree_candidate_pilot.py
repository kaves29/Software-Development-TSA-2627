"""Exploratory random-forest candidate ranking; never use as a final test."""

import argparse
import json
from zipfile import ZipFile

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import RandomForestClassifier
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference
from speech_analysis_onboarding_model.filler_frames import decode_frames

parser = argparse.ArgumentParser(
    description="Experimental speaker-separated forest comparison on cached candidate outputs."
)
parser.add_argument("--annotations", required=True)
parser.add_argument("--sdk-dir", required=True)
parser.add_argument("--acoustic-dir", required=True)
parser.add_argument("--label-dir", required=True)
parser.add_argument("recordings", nargs="+")
args = parser.parse_args()
names = args.recordings
if len(set(names)) != len(names) or len(names) < 3:
    parser.error("provide at least three unique speaker recordings")
with ZipFile(args.annotations) as archive:
    splits = recording_splits(archive)
    permitted = {
        row["recording"]: row["speaker"]
        for split in ("training", "development")
        for row in splits[split]
    }
    if not set(names) <= permitted.keys():
        parser.error("only AMI training or development recordings are allowed")
    if len({permitted[name] for name in names}) != len(names):
        parser.error("each recording must have a distinct global speaker")

data = {}
for name in names:
    with open(f"{args.sdk_dir}/{name}.recall.json") as source:
        a = json.load(source)
    p = np.load(f"{args.acoustic_dir}/{name}.npy")[:, 0]
    w = np.load(f"{args.label_dir}/{name}.frame.npy")
    with ZipFile(args.annotations) as z:
        refs = filler_reference(z, name, a["duration"])
    events = decode_frames(
        np.column_stack((1 - p, p, np.zeros_like(p))), a["duration"], 0.5, 6
    )
    features = []
    for e in events:
        center = (e["start_s"] + e["end_s"]) / 2
        start = max(0, int(e["start_s"] / 0.02))
        end = min(len(w), max(start + 1, round(e["end_s"] / 0.02)))
        averages = w[start:end, 1:3].mean(0)
        e["text"] = ["um", "uh"][averages.argmax()]
        distance = min(
            (abs(center - (v["start"] + v["end"]) / 2) for v in a["fillers"]),
            default=10,
        )
        overlapping = [
            v["confidence"]
            for v in a["fillers"]
            if abs(center - (v["start"] + v["end"]) / 2) <= 0.25
        ]
        features.append(
            [
                e["score"],
                e["end_s"] - e["start_s"],
                float(averages.max()),
                float(averages.min()),
                min(distance, 2),
                max(overlapping, default=0),
            ]
        )
    cost = np.ones((len(events), len(refs))) * 1000
    for i, e in enumerate(events):
        for j, r in enumerate(refs):
            err1 = abs(e["start_s"] - r["start_s"])
            err2 = abs(e["end_s"] - r["end_s"])
            if e["text"] == r["text"] and max(err1, err2) <= 0.25:
                cost[i, j] = err1 + err2
    ii, jj = linear_sum_assignment(cost)
    labels = np.zeros(len(events), dtype=int)
    for i, j in zip(ii, jj):
        if cost[i, j] < 1000:
            labels[i] = 1
    data[name] = (a["duration"], events, refs, np.array(features), labels)
for target in names:
    train = [n for n in names if n != target]
    x = np.concatenate([data[n][3] for n in train])
    y = np.concatenate([data[n][4] for n in train])
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=4,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=2,
    )
    model.fit(x, y)
    d, e, r, x, _ = data[target]
    prob = model.predict_proba(x)[:, 1]
    for threshold in (0.25, 0.5):
        chosen = [event for event, p in zip(e, prob) if p >= threshold]
        result = recording_event_metrics(
            [{"duration_s": d, "predicted": chosen, "reference": r}]
        )
        print(target, threshold, result, flush=True)

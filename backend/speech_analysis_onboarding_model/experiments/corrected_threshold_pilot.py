"""Re-evaluate acoustic thresholds with independent sigmoid decoding."""

import argparse
import json
from itertools import product
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference
from speech_analysis_onboarding_model.filler_frames import decode_hysteresis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--annotations", type=Path, required=True)
parser.add_argument("--sdk-dir", type=Path, required=True)
parser.add_argument("--acoustic-dir", type=Path, required=True)
parser.add_argument("--label-dir", type=Path, required=True)
parser.add_argument("--holdout", help="Score a fixed 0.2/0.1 rule on this recording")
parser.add_argument("recordings", nargs="+")
args = parser.parse_args()
names = args.recordings
if len(set(names)) != len(names) or len(names) < 3:
    parser.error("provide at least three unique recordings")
if args.holdout and args.holdout not in names:
    parser.error("holdout must be one of the provided recordings")
with ZipFile(args.annotations) as z:
    splits = recording_splits(z)
    allowed = {
        r["recording"]: r["speaker"]
        for part in ("training", "development")
        for r in splits[part]
    }
if not set(names) <= allowed.keys() or len({allowed[n] for n in names}) != len(names):
    parser.error("recordings must be non-test and have distinct speakers")
thresholds = (0.2, 0.3, 0.4, 0.5, 0.6)
windows = (0.1, 0.25, 0.5, 1.0)
rows = {}
for n in names:
    a = json.loads((args.sdk_dir / f"{n}.recall.json").read_text())
    p = np.load(args.acoustic_dir / f"{n}.npy", allow_pickle=False)[:, 0]
    w = np.load(args.label_dir / f"{n}.frame.npy", allow_pickle=False)
    with ZipFile(args.annotations) as z:
        refs = filler_reference(z, n, a["duration"])
    options = {}
    for t in thresholds:
        frames = np.column_stack((1 - p, p, np.zeros_like(p)))
        events = decode_hysteresis(
            frames, a["duration"], onset=t, continuation=t, min_frames=6, max_gap=0
        )
        for e in events:
            x = max(0, int(e["start_s"] / 0.02))
            y = min(len(w), max(x + 1, round(e["end_s"] / 0.02)))
            e["text"] = ["um", "uh"][w[x:y, 1:3].sum(0).argmax()]
        print("candidate_count", n, t, len(events), flush=True)
        for window in windows:
            kept = [
                e
                for e in events
                if any(
                    abs((e["start_s"] + e["end_s"]) / 2 - (u["start"] + u["end"]) / 2)
                    <= window
                    for u in a["fillers"]
                )
            ]
            options[(t, window)] = {
                "duration_s": a["duration"],
                "predicted": kept,
                "reference": refs,
            }
    rows[n] = options
if args.holdout:
    target = args.holdout
    result = rows[target][(0.2, 0.1)]
    sdk = json.loads((args.sdk_dir / f"{target}.recall.json").read_text())
    labels = np.load(args.label_dir / f"{target}.frame.npy", allow_pickle=False)
    baseline = []
    for event in sdk["fillers"]:
        start = max(0, int(event["start"] / 0.02))
        end = min(len(labels), max(start + 1, round(event["end"] / 0.02)))
        baseline.append({
            "start_s": event["start"],
            "end_s": event["end"],
            "text": ["um", "uh"][labels[start:end, 1:3].sum(0).argmax()],
        })
    print("fixed holdout", target, recording_event_metrics([result]))
    print("Uhm/WavLM baseline", target, recording_event_metrics([{
        **result, "predicted": baseline,
    }]))
    raise SystemExit(0)
scores = []
for target in names:
    train = [n for n in names if n != target]
    best = max(
        product(thresholds, windows),
        key=lambda k: (recording_event_metrics([rows[n][k] for n in train])["f1"], k),
    )
    r = rows[target][best]
    scores.append(r)
    print(
        "fold",
        target,
        "chosen",
        best,
        "result",
        recording_event_metrics([r]),
        flush=True,
    )
print("pooled", recording_event_metrics(scores), flush=True)
for setting in ((0.2, 0.1), (0.3, 0.1), (0.4, 0.1), (0.5, 0.1), (0.6, 0.1)):
    print(
        "fixed",
        setting,
        recording_event_metrics([rows[n][setting] for n in names]),
        flush=True,
    )

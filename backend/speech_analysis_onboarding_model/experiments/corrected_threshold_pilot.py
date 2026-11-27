"""Re-evaluate acoustic thresholds with independent sigmoid decoding."""

import argparse
import json
from itertools import product
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import (
    event_scores,
    recording_event_metrics,
)
from speech_analysis_onboarding_model.evaluate_ami import filler_reference
from speech_analysis_onboarding_model.filler_frames import decode_hysteresis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--annotations", type=Path, required=True)
parser.add_argument("--sdk-dir", type=Path, required=True)
parser.add_argument("--acoustic-dir", type=Path, required=True)
parser.add_argument("--label-dir", type=Path, required=True)
parser.add_argument("--holdout", help="Score a fixed 0.2/0.1 rule on this recording")
parser.add_argument("--hysteresis-grid", action="store_true")
parser.add_argument("--candidate-audit", action="store_true")
parser.add_argument("--rescue", action="store_true", help="Test high-confidence acoustic-only candidates")
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
decoder_settings = tuple((t, t, 0) for t in thresholds)
if args.hysteresis_grid:
    decoder_settings += tuple(
        (onset, continuation, gap)
        for onset, continuation, gap in product((0.3, 0.5, 0.7), (0.1, 0.2), (0, 3))
    )
windows = (0.1, 0.25, 0.5, 1.0)
rescue_levels = (1.1, 0.65, 0.8, 0.9, 0.95) if args.rescue else (1.1,)
rows = {}
for n in names:
    a = json.loads((args.sdk_dir / f"{n}.recall.json").read_text())
    p = np.load(args.acoustic_dir / f"{n}.npy", allow_pickle=False)[:, 0]
    w = np.load(args.label_dir / f"{n}.frame.npy", allow_pickle=False)
    with ZipFile(args.annotations) as z:
        refs = filler_reference(z, n, a["duration"])
    options = {}
    for t, continuation, gap in decoder_settings:
        frames = np.column_stack((1 - p, p, np.zeros_like(p)))
        events = decode_hysteresis(
            frames, a["duration"], onset=t, continuation=continuation, min_frames=6, max_gap=gap
        )
        for e in events:
            x = max(0, int(e["start_s"] / 0.02))
            y = min(len(w), max(x + 1, round(e["end_s"] / 0.02)))
            e["text"] = ["um", "uh"][w[x:y, 1:3].sum(0).argmax()]
        print("candidate_count", n, t, len(events), flush=True)
        if args.candidate_audit and (t, continuation, gap) == (0.2, 0.2, 0):
            sdk_events = [
                {"start_s": filler["start"], "end_s": filler["end"]}
                for filler in a["fillers"]
            ]
            untyped_refs = [{k: event[k] for k in ("start_s", "end_s")} for event in refs]
            untyped_acoustic = [{k: event[k] for k in ("start_s", "end_s")} for event in events]
            for source, candidates in (
                ("sdk", sdk_events),
                ("acoustic", untyped_acoustic),
                ("union", sdk_events + untyped_acoustic),
                ("acoustic typed", events),
            ):
                reference = refs if source == "acoustic typed" else untyped_refs
                score = event_scores(candidates, reference, 0.25)
                print("candidate audit", n, source, score["matches"], len(candidates), len(refs))

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
            for rescue in rescue_levels:
                predicted = [e for e in events if e in kept or e["score"] >= rescue]
                options[((t, continuation, gap), window, rescue)] = {
                    "duration_s": a["duration"],
                    "predicted": predicted,
                    "reference": refs,
                }
    rows[n] = options
if args.holdout:
    target = args.holdout
    result = rows[target][((0.2, 0.2, 0), 0.1, 1.1)]
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
        product(decoder_settings, windows, rescue_levels),
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
        recording_event_metrics([rows[n][((setting[0], setting[0], 0), setting[1], 1.1)] for n in names]),
        flush=True,
    )

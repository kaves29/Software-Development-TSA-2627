"""Score acoustic repetition reparanda on non-test AMI recordings."""

import argparse
from itertools import product
from pathlib import Path
from wave import open as wavopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.experiments.ami_repetition_pilot import (
    _word_ids,
    read_words,
)
from speech_analysis_onboarding_model.filler_frames import decode_hysteresis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("annotations", type=Path)
parser.add_argument("audio_dir", type=Path)
parser.add_argument("acoustic_dir", type=Path)
parser.add_argument("recordings", nargs="+")
parser.add_argument("--tune-durations", action="store_true")
args = parser.parse_args()
names = args.recordings
if len(set(names)) != len(names) or len(names) < 3:
    parser.error("provide at least three distinct recordings")
thresholds = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
settings = tuple(product(thresholds, (3, 6), (0, 2))) if args.tune_durations else tuple(
    (threshold, 3, 0) for threshold in thresholds
)
data = {}
with ZipFile(args.annotations) as z:
    splits = recording_splits(z)
    allowed = {
        r["recording"]: r["speaker"]
        for sp in ("training", "development")
        for r in splits[sp]
    }
    if not set(names) <= allowed.keys() or len({allowed[n] for n in names}) != len(
        names
    ):
        parser.error("only non-test recordings from distinct speakers are allowed")
    for n in names:
        _, byid = read_words(z, n)
        root = ET.fromstring(z.read(f"disfluency/{n}.disfluency.xml"))
        refs = []
        for parent in root.iter("dsfl"):
            if not any(
                c.tag.endswith("pointer")
                and c.get("role") == "dsfl-type"
                and c.get("href", "").endswith("id(ami_dsfl_12)")
                for c in parent
            ):
                continue
            for node in parent.iter("dsfl"):
                if not any(
                    c.tag.endswith("pointer")
                    and c.get("role") == "dsfl-type"
                    and c.get("href", "").endswith("id(ami_dsfl_19)")
                    for c in node
                ):
                    continue
                ids = [
                    j
                    for c in node.iter()
                    if c.tag.endswith("child")
                    for j in _word_ids(c.get("href", ""))
                ]
                selected = [byid[k] for k in ids if k in byid]
                if not selected:
                    raise ValueError("unresolved")
                refs.append(
                    {
                        "start_s": min(w[1] for w in selected),
                        "end_s": max(w[2] for w in selected),
                    }
                )
        with wavopen(str(args.audio_dir / f"{n}.wav")) as wav:
            dur = wav.getnframes() / wav.getframerate()
        p = np.load(args.acoustic_dir / f"{n}.npy", allow_pickle=False)[:, 1]
        frame_ref = np.zeros(len(p), bool)
        for r in refs:
            frame_ref[
                max(0, int(r["start_s"] / 0.02)) : min(
                    len(p), int(np.ceil(r["end_s"] / 0.02))
                )
            ] = True
        data[n] = {}
        for t, min_frames, max_gap in settings:
            events = decode_hysteresis(
                np.column_stack((1 - p, p, np.zeros_like(p))),
                dur,
                onset=t,
                continuation=t,
                min_frames=min_frames,
                max_gap=max_gap,
            )
            pred = [{"start_s": e["start_s"], "end_s": e["end_s"]} for e in events]
            r = {"duration_s": dur, "predicted": pred, "reference": refs}
            active = p >= t
            tp = int((active & frame_ref).sum())
            fp = int((active & ~frame_ref).sum())
            fn = int((~active & frame_ref).sum())
            data[n][(t, min_frames, max_gap)] = (r, (tp, fp, fn))
        print(
            n,
            "ref",
            len(refs),
            "default",
            recording_event_metrics([data[n][(0.5, 3, 0)][0]]),
            flush=True,
        )
for t, min_frames, max_gap in settings:
    row = [data[n][(t, min_frames, max_gap)][0] for n in names]
    tp, fp, fn = np.sum([data[n][(t, min_frames, max_gap)][1] for n in names], axis=0)
    print(
        "fixed",
        (t, min_frames, max_gap),
        "events",
        recording_event_metrics(row),
        "frame",
        {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "f1": float(2 * tp / (2 * tp + fp + fn)),
        },
        flush=True,
    )
outer = []
for name in names:
    train = [n for n in names if n != name]
    best = max(
        settings,
        key=lambda setting: (
            recording_event_metrics([data[n][setting][0] for n in train])["f1"] or 0,
            setting,
        ),
    )
    r = data[name][best][0]
    outer.append(r)
    print("fold", name, best, recording_event_metrics([r]), flush=True)
print("nested", recording_event_metrics(outer), flush=True)

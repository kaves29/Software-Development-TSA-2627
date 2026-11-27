"""Score repeated-word events against AMI annotations on non-test recordings.

The oracle mode uses human word transcripts to isolate the rule from ASR errors.
"""

import argparse
import json
import re
from pathlib import Path
from wave import open as open_wave
from xml.etree import ElementTree
from zipfile import ZipFile

from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.analysis import analyze_features
from speech_analysis_onboarding_model.evaluate import recording_event_metrics

NITE_ID = "{http://nite.sourceforge.net/}id"


def read_words(archive, name):
    with archive.open(f"words/{name}.words.xml") as stream:
        root = ElementTree.parse(stream).getroot()
    words, by_id = [], {}
    for word in root.iter("w"):
        start, end = word.get("starttime"), word.get("endtime")
        text = (word.text or "").strip()
        if (
            not start
            or not end
            or word.get("punc") == "true"
            or float(start) >= float(end)
            or not text
        ):
            continue
        entry = (text, float(start), float(end))
        words.append(entry)
        by_id[word.get(NITE_ID)] = entry
    return words, by_id


def _word_ids(href):
    ids = re.findall(r"id\(([^)]+)\)", href)
    if len(ids) != 2:
        return ids
    first = re.fullmatch(r"(.*?)(\d+)", ids[0])
    last = re.fullmatch(r"(.*?)(\d+)", ids[1])
    if (
        not first
        or not last
        or first.group(1) != last.group(1)
        or int(first.group(2)) > int(last.group(2))
    ):
        raise ValueError("unsupported AMI word range")
    return [
        first.group(1) + str(index)
        for index in range(int(first.group(2)), int(last.group(2)) + 1)
    ]


def reference_repetitions(archive, name, by_id):
    with archive.open(f"disfluency/{name}.disfluency.xml") as stream:
        root = ElementTree.parse(stream).getroot()
    events = []
    for node in root.iter("dsfl"):
        if not any(
            child.tag.endswith("pointer")
            and child.get("role") == "dsfl-type"
            and child.get("href", "").endswith("id(ami_dsfl_12)")
            for child in node
        ):
            continue
        ids = [
            identity
            for child in node.iter()
            if child.tag.endswith("child")
            for identity in _word_ids(child.get("href", ""))
        ]
        selected = [by_id[identity] for identity in ids if identity in by_id]
        if not selected:
            raise ValueError(f"unresolved repetition in {name}")
        events.append(
            {
                "start_s": min(row[1] for row in selected),
                "end_s": max(row[2] for row in selected),
            }
        )
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("audio_dir", type=Path)
    parser.add_argument("recordings", nargs="+")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--word-cache-dir", type=Path,
                        help="Score timestamped transcription from RECORDING.crisper-words.json")
    inputs.add_argument(
        "--prediction-dir",
        type=Path,
        help="Score existing analysis JSON instead of oracle words",
    )
    parser.add_argument("--acoustic-dir", type=Path, help="Filter ASR repeats using cached acoustic scores")
    parser.add_argument("--acoustic-min-peak", type=float, default=0.2)
    args = parser.parse_args()
    if args.acoustic_dir and not args.word_cache_dir:
        parser.error("--acoustic-dir requires --word-cache-dir")
    if not args.recordings or len(set(args.recordings)) != len(args.recordings):
        parser.error("recordings must be unique")
    with ZipFile(args.annotations) as archive:
        splits = recording_splits(archive)
        permitted = {
            row["recording"]: row["speaker"]
            for split in ("training", "development")
            for row in splits[split]
        }
        if not set(args.recordings) <= permitted.keys() or len(
            {permitted[n] for n in args.recordings}
        ) != len(args.recordings):
            parser.error("recordings must be non-test and have distinct speakers")
        rows = []
        for name in args.recordings:
            words, by_id = read_words(archive, name)
            reference = reference_repetitions(archive, name, by_id)
            with open_wave(str(args.audio_dir / f"{name}.wav")) as wav:
                duration = wav.getnframes() / wav.getframerate()
            if args.prediction_dir:
                result = json.loads((args.prediction_dir / f"{name}.json").read_text())
                feature = result["features"]["repetitions"]
                prediction = (
                    feature.get("value")
                    if feature.get("status")
                    not in {"unavailable", "insufficient_evidence"}
                    else None
                )
            else:
                if args.word_cache_dir:
                    path = args.word_cache_dir / f"{name}.crisper-words.json"
                    rows_from_asr = json.loads(path.read_text())
                    words = [
                        (row["word"], row["start"], row["end"])
                        for row in rows_from_asr
                        if row["word"].strip().lower() not in {"[breath]", "[noise]", "[laughter]"}
                    ]
                prediction = analyze_features(duration, [(0, duration)], words, [])[
                    "repetitions"
                ]["value"]
            if prediction is not None:
                prediction = [
                    {"start_s": e["start_s"], "end_s": e["end_s"]} for e in prediction
                ]
            if args.acoustic_dir:
                import numpy as np

                scores = np.load(args.acoustic_dir / f"{name}.npy", allow_pickle=False)[:, 1]
                prediction = [
                    event for event in prediction
                    if scores[int(event["start_s"] * 50):int(event["end_s"] * 50) + 1]
                    .max(initial=0) >= args.acoustic_min_peak
                ]
            row = {
                "duration_s": duration,
                "predicted": prediction,
                "reference": reference,
            }
            rows.append(row)
            print(name, json.dumps(recording_event_metrics([row])), flush=True)
        print("pooled", json.dumps(recording_event_metrics(rows)), flush=True)


if __name__ == "__main__":
    main()

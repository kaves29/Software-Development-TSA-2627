"""Compare full-recording voice pauses to between-word gaps on AMI development data.

These word-boundary gaps are an imperfect proxy for acoustic silence; the
recordings are not a final speaker-held-out test for this project.
"""

import argparse
import itertools
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import torch
from silero_vad import get_speech_timestamps, load_silero_vad
from speech_analysis_onboarding_model.__main__ import SAMPLE_RATE, decode_audio
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.evaluate import recording_event_metrics

MIN_PAUSE, MAX_PAUSE = 0.8, 2.0
THRESHOLDS = (0.3, 0.5, 0.7)


def reference_pauses(archive, name, duration):
    with archive.open(f"words/{name}.words.xml") as stream:
        root = ElementTree.parse(stream).getroot()
    words = sorted(
        (float(word.attrib["starttime"]), float(word.attrib["endtime"]))
        for word in root.iter("w")
        if word.get("punc") != "true"
        and word.get("starttime") is not None
        and word.get("endtime") is not None
        and 0
        <= float(word.attrib["starttime"])
        < float(word.attrib["endtime"])
        <= duration
    )
    merged = []
    for start, end in words:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return [
        {"start_s": previous_end, "end_s": next_start}
        for (_, previous_end), (next_start, _) in itertools.pairwise(merged)
        if MIN_PAUSE <= next_start - previous_end <= MAX_PAUSE
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("audio_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("recordings", nargs="+")
    args = parser.parse_args()
    if len(set(args.recordings)) != len(args.recordings) or len(args.recordings) < 3:
        parser.error("provide at least three distinct recordings")
    with ZipFile(args.annotations) as archive:
        splits = recording_splits(archive)
        permitted = {
            row["recording"]: (split, row["speaker"])
            for split in ("training", "development")
            for row in splits[split]
        }
        if not set(args.recordings) <= permitted.keys():
            parser.error(
                "only official training and development recordings are permitted"
            )
        if len({permitted[name][1] for name in args.recordings}) != len(
            args.recordings
        ):
            parser.error("recordings must have distinct speakers")
        torch.set_num_threads(2)
        model = load_silero_vad()
        rows = []
        for name in args.recordings:
            wave = decode_audio(args.audio_dir / f"{name}.wav", 3600)
            duration = len(wave) / SAMPLE_RATE
            reference = reference_pauses(archive, name, duration)
            settings = {}
            for threshold in THRESHOLDS:
                speech = get_speech_timestamps(
                    torch.from_numpy(wave),
                    model,
                    sampling_rate=SAMPLE_RATE,
                    threshold=threshold,
                )
                events = [
                    {
                        "start_s": left["end"] / SAMPLE_RATE,
                        "end_s": right["start"] / SAMPLE_RATE,
                    }
                    for left, right in itertools.pairwise(speech)
                    if MIN_PAUSE
                    <= (right["start"] - left["end"]) / SAMPLE_RATE
                    <= MAX_PAUSE
                ]
                item = {
                    "duration_s": duration,
                    "predicted": events,
                    "reference": reference,
                }
                settings[str(threshold)] = {
                    "events": events,
                    "score_250ms": recording_event_metrics([item]),
                    "score_500ms": recording_event_metrics([item], tolerance=0.5),
                }
            rows.append(
                {
                    "recording": name,
                    "split": permitted[name][0],
                    "speaker": permitted[name][1],
                    "duration_s": duration,
                    "reference": reference,
                    "settings": settings,
                }
            )
            args.output.write_text(json.dumps(rows, indent=2))
            print(
                name,
                "seconds",
                round(duration),
                "reference",
                len(reference),
                "F1",
                {
                    t: round(v["score_250ms"]["f1"], 4)
                    if v["score_250ms"]["f1"] is not None
                    else None
                    for t, v in settings.items()
                },
                flush=True,
            )


if __name__ == "__main__":
    main()

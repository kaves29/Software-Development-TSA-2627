"""Evaluate released CrisperWhisper inference on complete AMI development tracks."""

import argparse
import json
from pathlib import Path
from wave import open as open_wave
from zipfile import ZipFile

from .ami_split import recording_splits
from .evaluate import recording_event_metrics
from .evaluate_ami import filler_reference


def filler_events(words):
    events = []
    for word in words:
        label = word.word.casefold().strip(" []<>.,?!;:")
        if label in {"um", "uh"}:
            events.append({"text": label, "start_s": word.start, "end_s": word.end})
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("audio", type=Path, nargs="+", metavar="MEETING.SPEAKER.wav")
    parser.add_argument(
        "--model", choices=("small", "turbo", "medium", "large"), default="small"
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    with ZipFile(args.annotations) as archive:
        split = recording_splits(archive)
        development = {row["recording"] for row in split["development"]}
        requested = {path.stem for path in args.audio}
        if not requested <= development or len(requested) != len(args.audio):
            parser.error("provide unique recordings from AMI development only")
        from crisperwhisper import CrisperWhisperModel

        model = CrisperWhisperModel(
            args.model,
            device=args.device,
            compute_type="int8" if args.device == "cpu" else "float16",
            cache_dir=args.cache_dir,
        )
        rows = []
        for path in args.audio:
            with open_wave(str(path)) as stream:
                duration = stream.getnframes() / stream.getframerate()
            reference = filler_reference(archive, path.stem, duration)
            result = model.transcribe(str(path), language="en", word_timestamps=True)
            row = {
                "duration_s": duration,
                "predicted": filler_events(result.words),
                "reference": reference,
            }
            rows.append(row)
            print(
                json.dumps({"recording": path.stem, **recording_event_metrics([row])}),
                flush=True,
            )
        print(json.dumps({"pooled": recording_event_metrics(rows)}), flush=True)


if __name__ == "__main__":
    main()

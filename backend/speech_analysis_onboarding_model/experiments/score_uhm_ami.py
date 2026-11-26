"""Score cached untyped Uhm events on two previously used AMI training recordings."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("prediction_directory", type=Path)
    args = parser.parse_args()
    rows = []
    # Deliberately fixed: cannot accidentally inspect an official test recording.
    with ZipFile(args.annotations) as archive:
        for recording in ("ES2005a.A", "ES2006a.A"):
            raw = json.loads(
                (args.prediction_directory / f"{recording}.recall.json").read_text()
            )
            reference = filler_reference(archive, recording, raw["duration"])
            for event in reference:
                event["text"] = "filler"
            predicted = [
                {"start_s": event["start"], "end_s": event["end"], "text": "filler"}
                for event in raw["fillers"]
            ]
            row = {
                "duration_s": raw["duration"],
                "reference": reference,
                "predicted": predicted,
            }
            rows.append(row)
            print(recording, json.dumps(recording_event_metrics([row])))
    print("pooled", json.dumps(recording_event_metrics(rows)))


if __name__ == "__main__":
    main()

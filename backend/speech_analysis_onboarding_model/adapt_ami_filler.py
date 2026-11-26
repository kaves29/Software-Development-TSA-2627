"""Compare a training-only WavLM head adaptation on complete AMI development audio."""

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import torch
from speech_analysis_onboarding_model.__main__ import decode_audio
from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.ami_training import FIELDS, word_rows
from speech_analysis_onboarding_model.evaluate import recording_event_metrics
from speech_analysis_onboarding_model.evaluate_ami import filler_reference
from speech_analysis_onboarding_model.filler_frames import (
    decode_frames,
    score_recording,
)
from speech_analysis_onboarding_model.fillers import ENCODERS, load_checkpoint
from speech_analysis_onboarding_model.train_filler_frames import (
    ContinuousWindows,
    FrameClassifier,
)
from transformers import AutoModel


def main():
    parser = argparse.ArgumentParser(
        description="Adapt a frozen WavLM filler head using AMI training audio."
    )
    parser.add_argument("annotations", type=Path)
    parser.add_argument("audio_dir", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--train", action="append", required=True)
    parser.add_argument("--development", required=True)
    parser.add_argument("--windows-per-track", type=int, default=60)
    parser.add_argument(
        "--original-scores",
        type=Path,
        help="Cached frame probabilities for the development track",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    root, out = args.audio_dir, args.output
    train, development = args.train, args.development
    if len(set(train)) != len(train) or args.windows_per_track < 1:
        parser.error("provide unique training recordings and a positive window count")
    with ZipFile(args.annotations) as archive:
        splits = recording_splits(archive)
        if not set(train) <= {row["recording"] for row in splits["training"]}:
            parser.error("all training recordings must be assigned to AMI training")
        if development not in {row["recording"] for row in splits["development"]}:
            parser.error("the comparison recording must be assigned to AMI development")
        out.mkdir(parents=True, exist_ok=False)
        with (out / "words.csv").open("w", newline="") as destination:
            writer = csv.writer(destination)
            writer.writerow(FIELDS)
            writer.writerows(row for row in word_rows(archive) if row[0] in train)
    for recording in train:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(root / f"{recording}.wav"),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(out / f"{recording}.wav"),
            ],
            check=True,
        )
    dataset = ContinuousWindows(out, out / "words.csv", "train", window_hop_seconds=2)
    indices = {name: [] for name in train}
    for i, (path, _) in enumerate(dataset.windows):
        indices[path.stem].append(i)
    rng = np.random.default_rng(42)
    selection = [
        int(i)
        for group in indices.values()
        for i in rng.choice(
            group, min(len(group), args.windows_per_track), replace=False
        )
    ]
    inputs = [
        args.annotations,
        args.checkpoint,
        *(root / f"{name}.wav" for name in (*train, development)),
    ]
    provenance = {}
    for path in inputs:
        with path.open("rb") as stream:
            provenance[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    (out / "inputs.json").write_text(
        json.dumps(
            {
                "sha256": provenance,
                "training_windows": [
                    str(dataset.windows[index][0].stem)
                    + ":"
                    + str(dataset.windows[index][1])
                    for index in selection
                ],
                "development": development,
                "seed": 42,
            },
            indent=2,
        )
        + "\n"
    )
    torch.manual_seed(42)
    torch.set_num_threads(2)
    checkpoint = args.checkpoint
    metadata = torch.load(checkpoint, map_location="cpu", weights_only=True)
    name, revision = ENCODERS["wavlm"]
    if (
        metadata.get("kind"),
        metadata.get("encoder_name"),
        metadata.get("revision"),
        metadata.get("window_samples"),
    ) != ("frame_filler", "wavlm", revision, 64000):
        raise ValueError(
            "expected a four-second frame checkpoint with the pinned WavLM encoder"
        )
    model = (
        FrameClassifier(
            AutoModel.from_pretrained(name, revision=revision), encoder_name="wavlm"
        )
        .to(args.device)
        .eval()
    )
    load_checkpoint(model, checkpoint)
    original_head = {
        key: value.detach().clone() for key, value in model.head.state_dict().items()
    }
    features = []
    labels = []
    with torch.no_grad():
        for i in range(0, len(selection), 4):
            batch = [dataset[j] for j in selection[i : i + 4]]
            waveforms = torch.stack([audio for audio, _ in batch]).to(args.device)
            normalized = (waveforms - waveforms.mean(-1, keepdim=True)) / (
                waveforms.var(-1, keepdim=True, unbiased=False) + 1e-7
            ).sqrt()
            features.append(model.encoder(normalized).last_hidden_state.flatten(0, 1))
            labels.append(torch.stack([label for _, label in batch]).flatten())
    x, y = torch.cat(features), torch.cat(labels).to(args.device)
    x, y = x[y >= 0], y[y >= 0]
    counts = y.bincount(minlength=3)
    print("training frames per class", counts.tolist(), flush=True)
    if min(counts).item() == 0:
        raise ValueError("sampled training windows lack a class")
    weights = (counts.float().sum() / counts.float()).sqrt()
    optimizer = torch.optim.AdamW(model.head.parameters(), lr=0.0003)
    for epoch in range(5):
        for batch in torch.randperm(len(y), device=args.device).split(512):
            optimizer.zero_grad()
            loss = torch.nn.functional.cross_entropy(
                model.head(x[batch]), y[batch], weight=weights
            )
            loss.backward()
            optimizer.step()
        print(
            "epoch",
            epoch + 1,
            "weighted loss",
            torch.nn.functional.cross_entropy(model.head(x), y, weight=weights).item(),
            flush=True,
        )
    torch.save(
        {
            "head": model.head.state_dict(),
            "encoder_name": "wavlm",
            "kind": "frame_filler",
            "revision": revision,
            "window_samples": 64000,
        },
        out / "head.pt",
    )
    waveform = decode_audio(root / f"{development}.wav", 3600)
    duration = len(waveform) / 16000
    if not 0 < duration <= 3600:
        raise ValueError(
            "expected a complete nonempty development recording up to one hour"
        )
    with ZipFile(args.annotations) as archive:
        refs = filler_reference(archive, development, duration)
    probabilities = score_recording(
        model, waveform, batch_size=4, window_samples=64000, device=args.device
    )
    np.save(out / "development.npy", probabilities)
    if args.original_scores:
        original = np.load(args.original_scores, allow_pickle=False)
        if original.shape != probabilities.shape:
            raise ValueError(
                "cached original scores do not match the development recording length"
            )
    else:
        model.head.load_state_dict(original_head)
        original = score_recording(
            model, waveform, batch_size=4, window_samples=64000, device=args.device
        )
    for tag, scores in [("original", original), ("adapted", probabilities)]:
        for threshold in (0.60, 0.80):
            predictions = decode_frames(scores, duration, threshold, 12)
            print(
                tag,
                threshold,
                recording_event_metrics(
                    [
                        {
                            "duration_s": duration,
                            "predicted": predictions,
                            "reference": refs,
                        }
                    ]
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()

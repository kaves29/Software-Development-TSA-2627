"""Verify cached verbatim filler proposals using the WavLM acoustic head."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .ami_references import word_references
from .evaluate import recording_event_metrics
from .verbatim import level_gated_fillers

RATE = 16000
WINDOW = 64000
FILLERS = ('um', 'uh')


def acoustic_scores(model, waveform, events):
    """Score each interval in a centered four-second acoustic window."""
    import torch

    def window(start):
        clip = waveform[start:start + WINDOW]
        return np.pad(clip, (0, WINDOW - len(clip)))

    offsets = [
        max(0, round(((event['start_s'] + event['end_s']) / 2 - 2) * RATE))
        for event in events
    ]
    result = []
    model.eval()
    with torch.inference_mode():
        for base in range(0, len(events), 4):
            starts = offsets[base:base + 4]
            clips = torch.from_numpy(np.stack([window(start) for start in starts]))
            probabilities = model(clips).softmax(-1).cpu().numpy()
            for index, (start, frames) in enumerate(zip(starts, probabilities), base):
                event = events[index]
                centers = (start + np.arange(len(frames)) * 320 + 199.5) / RATE
                eligible = ((centers >= event['start_s'] - .04)
                            & (centers <= event['end_s'] + .04))
                scores = frames[eligible].mean(axis=0) if eligible.any() else np.zeros(3)
                result.append({**event, 'class_scores': dict(zip(FILLERS, map(float, scores[1:])))})
    return result


def verified_events(events, *, relabel=False):
    findings = []
    for event in events:
        scores = event['class_scores']
        label = max(FILLERS, key=scores.__getitem__) if relabel else event['text']
        if scores[label] >= .50:
            findings.append({**event, 'text': label})
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('cache', type=Path, help='JSON written by evaluate_verbatim --event-cache')
    parser.add_argument('encoder', type=Path)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('recordings', nargs='+', type=Path)
    args = parser.parse_args()

    import soundfile as sf
    import torch
    from transformers import AutoModel

    from .fillers import load_checkpoint
    from .train_filler_frames import FrameClassifier

    cached = json.loads(args.cache.read_text())
    if len({path.stem for path in args.recordings}) != len(args.recordings):
        parser.error('recording IDs must be unique')
    torch.set_num_threads(2)
    model = FrameClassifier(AutoModel.from_pretrained(args.encoder, local_files_only=True),
                            encoder_name='wavlm')
    load_checkpoint(model, args.checkpoint)
    measures = {mode: {label: [] for label in FILLERS}
                for mode in ('verbatim', 'level', 'agreement', 'relabel')}
    with ZipFile(args.annotations) as archive:
        for path in args.recordings:
            samples, rate = sf.read(path, dtype='float32')
            duration = len(samples) / rate
            payload = cached[path.stem]
            with path.open('rb') as media:
                digest = hashlib.file_digest(media, 'sha256').hexdigest()
            if (rate != RATE or samples.ndim != 1 or digest != payload['sha256']
                    or abs(duration - payload['duration_s']) > 1 / RATE):
                raise ValueError(f'{path}: expected the same mono 16 kHz audio used in the ASR run')
            reference = word_references(archive, path.stem, duration)
            events = payload['events'] or []
            gated = level_gated_fillers(events, samples, rate)
            scored = acoustic_scores(model, samples, gated)
            for mode, prediction in (
                ('verbatim', events), ('level', gated),
                ('agreement', verified_events(scored)),
                ('relabel', verified_events(scored, relabel=True)),
            ):
                for label in FILLERS:
                    measures[mode][label].append({
                        'duration_s': duration, 'reference': reference[label],
                        'predicted': [event for event in prediction if event['text'] == label],
                    })
    print(json.dumps({
        mode: {label: recording_event_metrics(rows) for label, rows in labels.items()}
        for mode, labels in measures.items()
    }, indent=2))


if __name__ == '__main__':
    main()

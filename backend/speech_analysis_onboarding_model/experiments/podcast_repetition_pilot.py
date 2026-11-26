"""Score acoustic repetition probabilities on selected PodcastFillers windows.

The labels are selected candidates, not exhaustive event annotations. This
therefore measures oracle-window classification, not end-to-end detection.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def windows(metadata, scores_path, episode, split, duration):
    rows = metadata.loc[
        (metadata.podcast_filename == episode)
        & (metadata.episode_split_subset == split)
        & metadata.label_full_vocab.isin(["Words", "Repetitions"])
        & (metadata.event_start_inepisode >= 0)
        & (metadata.event_end_inepisode <= duration)
    ]
    if rows.empty:
        raise ValueError("No labeled windows matched the requested episode and split")
    scores = np.load(scores_path)
    if scores.ndim != 2 or scores.shape[1] < 2 or len(scores) < duration * 50:
        raise ValueError("Expected 50 Hz frame probabilities covering the full excerpt")
    means, labels = [], []
    for row in rows.itertuples():
        start = max(0, int(row.event_start_inepisode * 50))
        end = min(len(scores), max(start + 1, int(np.ceil(row.event_end_inepisode * 50))))
        means.append(float(np.mean(scores[start:end, 1])))
        labels.append(row.label_full_vocab == "Repetitions")
    return np.array(means), np.array(labels)


def metrics(means, labels, threshold):
    predicted = means >= threshold
    tp = int(np.sum(predicted & labels))
    fp = int(np.sum(predicted & ~labels))
    fn = int(np.sum(~predicted & labels))
    tn = int(np.sum(~predicted & ~labels))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("scores", type=Path)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--split", choices=("train", "validation"), required=True)
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--train", nargs=2, action="append", default=[],
                        metavar=("EPISODE", "SCORES"),
                        help="Training episode and cached scores; may be repeated")
    args = parser.parse_args()

    metadata = pd.read_csv(args.metadata)
    threshold = 0.5
    if args.train:
        if args.split != "validation" or args.episode in [item[0] for item in args.train]:
            raise ValueError("Calibration requires distinct training and validation episodes")
        train = [windows(metadata, Path(path), episode, "train", args.duration)
                 for episode, path in args.train]
        train_scores = np.concatenate([item[0] for item in train])
        train_labels = np.concatenate([item[1] for item in train])
        grid = (0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5)
        threshold = max(grid, key=lambda value: (metrics(train_scores, train_labels, value)["f1"], value))
        print(json.dumps({"training_threshold": threshold,
                          "training": metrics(train_scores, train_labels, threshold)}))
    means, labels = windows(metadata, args.scores, args.episode, args.split, args.duration)
    print(json.dumps({"threshold": threshold, **metrics(means, labels, threshold)}))


if __name__ == "__main__":
    main()

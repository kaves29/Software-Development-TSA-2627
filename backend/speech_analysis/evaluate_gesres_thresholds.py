"""Compare an exploratory wrist-speed proxy against GESRes gesture-speed labels.

Select the threshold on one annotated video and freeze it for a second video.
The datasets' speed categories differ from the wrist-speed fraction, so results
are proxy scores, not validated feedback or a production recommendation.
"""

import argparse
import json
import math
from pathlib import Path

THRESHOLDS = tuple(i / 10 for i in range(10))


def score(rows, threshold):
    tp = fp = fn = tn = abstained = labeled = 0
    positives = negatives = 0
    for row in rows:
        label = row['speed_label']
        if label not in ('fast', 'medium', 'slow'):
            continue
        labeled += 1
        positives += label == 'fast'
        negatives += label != 'fast'
        value = row['rapid_motion']['value']
        if value is None:
            abstained += 1
            fn += label == 'fast'
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('rapid motion must be a fraction or null')
        predicted = value > 0 if threshold == 0 else value >= threshold
        if label == 'fast':
            tp += predicted
            fn += not predicted
        elif predicted:
            fp += 1
        else:
            tn += 1
    if not positives or not negatives:
        raise ValueError('each video needs both fast and nonfast labeled gestures')
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'abstained': abstained,
            'labeled': labeled, 'coverage': (labeled - abstained) / labeled,
            'f1': 2 * tp / (2 * tp + fp + fn)}


def compare(development, evaluation):
    if not development.get('video_id') or not evaluation.get('video_id') or development['video_id'] == evaluation['video_id']:
        raise ValueError('provide distinct video identifiers')
    if development.get('fps') != 10 or evaluation.get('fps') != 10:
        raise ValueError('this exploratory comparison requires 10 fps for both videos')
    trials = [(score(development['results'], threshold)['f1'], threshold) for threshold in THRESHOLDS]
    selected = max(trials, key=lambda item: (item[0], -item[1]))[1]
    return {'note': 'Exploratory proxy, labels differ; positive abstentions count as misses, negative abstentions excluded.',
            'selected_threshold': selected,
            'development': score(development['results'], selected),
            'evaluation_baseline_nonzero': score(evaluation['results'], 0),
            'evaluation': score(evaluation['results'], selected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('development', type=Path)
    parser.add_argument('evaluation', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.development.read_text()),
                             json.loads(args.evaluation.read_text())), indent=2))


if __name__ == '__main__':
    main()

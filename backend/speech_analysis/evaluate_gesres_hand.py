"""Exploratory comparison of gesture-hand labels with relative wrist motion.

A gesture's annotated hand and the wrist with greater median movement are not
identical concepts; use this as a diagnostic, not a speaking-skill assessment.
"""

import argparse
import json
import math
from pathlib import Path


def score(rows):
    counts = {side: {'labeled': 0, 'usable': 0, 'correct': 0} for side in ('LH', 'RH')}
    for row in rows:
        label = row['hand_label']
        if label not in counts:
            continue
        info = counts[label]
        info['labeled'] += 1
        left = row['left_hand_motion']['value']
        right = row['right_hand_motion']['value']
        for value in (left, right):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('hand motion must be nonnegative or null')
        if left is None or right is None or left == right:
            continue
        info['usable'] += 1
        predicted = 'LH' if left > right else 'RH'
        info['correct'] += predicted == label
    total = sum(c['labeled'] for c in counts.values())
    usable = sum(c['usable'] for c in counts.values())
    correct = sum(c['correct'] for c in counts.values())
    if not total:
        raise ValueError('no one-handed labeled clips')
    return {'labeled_clips': total, 'usable_clips': usable, 'correct': correct,
            'coverage': usable / total,
            'accuracy_counting_abstentions_as_misses': correct / total,
            'accuracy_on_usable_clips': correct / usable if usable else None,
            'by_hand': counts,
            'note': 'Annotated gesture hand and greater wrist motion are different concepts; exploratory comparison only.'}


def score_both(rows):
    """Compare similar wrist-motion amounts with two-handed gesture annotations."""
    tp = fp = fn = tn = abstained = total = 0
    for row in rows:
        label = row['hand_label']
        if label not in ('LH', 'RH', 'both'):
            continue
        total += 1
        left = row['left_hand_motion']['value']
        right = row['right_hand_motion']['value']
        for value in (left, right):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('hand motion must be nonnegative or null')
        if left is None or right is None or max(left, right) == 0:
            abstained += 1
            fn += label == 'both'
            continue
        predicted = min(left, right) / max(left, right) >= .5
        if label == 'both':
            tp += predicted
            fn += not predicted
        elif predicted:
            fp += 1
        else:
            tn += 1
    if not total:
        raise ValueError('no labeled clips')
    denominator = 2 * tp + fp + fn
    return {'labeled_clips': total, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'abstained': abstained, 'coverage': (total - abstained) / total,
            'f1': 2 * tp / denominator if denominator else None,
            'note': 'Exploratory two-hand proxy; positive abstentions count as misses, negative abstentions excluded.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', type=Path)
    args = parser.parse_args()
    report = json.loads(args.observations.read_text())
    print(json.dumps({'fps': report['fps'], **score(report['results']),
                      'both_hand_proxy': score_both(report['results'])}, indent=2))


if __name__ == '__main__':
    main()

"""Score one analysis JSON against a manually annotated recording."""

import argparse
import json
from pathlib import Path


def event_scores(predicted, reference, tolerance):
    candidates = []
    for event in predicted:
        eligible = []
        for index, target in enumerate(reference):
            start = abs(event['start_s'] - target['start_s'])
            end = abs(event['end_s'] - target['end_s'])
            if max(start, end) <= tolerance and event.get('text') == target.get('text'):
                eligible.append(((start + end) / 2, index))
        candidates.append(sorted(eligible))

    # An augmenting path can move an earlier prediction to a different
    # reference, so a locally close match cannot hide a second true positive.
    assignments = {}
    for prediction in range(len(predicted)):
        queue = [prediction]
        visited_predictions = {prediction}
        predecessors = {}
        for current in queue:
            available = None
            for error, target in candidates[current]:
                if target in predecessors:
                    continue
                predecessors[target] = (current, error)
                if target not in assignments:
                    available = target
                    break
                previous, _ = assignments[target]
                if previous not in visited_predictions:
                    visited_predictions.add(previous)
                    queue.append(previous)
            if available is not None:
                break
        else:
            continue
        targets_by_prediction = {owner: target for target, (owner, _) in assignments.items()}
        while available is not None:
            current, error = predecessors[available]
            assignments[available] = current, error
            available = targets_by_prediction.get(current)
    errors = [error for _, error in assignments.values()]
    matches = len(errors)
    return {'matches': matches, 'predictions': len(predicted), 'references': len(reference),
            'precision': matches / len(predicted) if predicted else None,
            'recall': matches / len(reference) if reference else None,
            'mean_boundary_error_s': sum(errors) / matches if matches else None}


def score(features, reference):
    result = {}
    for key in ('pauses', 'fillers', 'repetitions', 'revisions'):
        if key in reference:
            value = features[key]['value']
            result[key] = (event_scores(value, reference[key], 0.25)
                           if value is not None else {'status': features[key]['status']})
    if 'hand_near_face' in reference:
        feature = features.get('hand_near_face', {})
        intervals = feature.get('intervals')
        if intervals is None:
            result['hand_near_face'] = {'status': 'insufficient_evidence'}
        else:
            events = event_scores(intervals, reference['hand_near_face'], 0.25)
            total = events['predictions'] + events['references']
            result['hand_near_face'] = {**events, 'f1': 2 * events['matches'] / total if total else None}
    if 'hand_near_face_returns' in reference:
        expected = reference['hand_near_face_returns']
        if type(expected) is not int or expected < 0:
            raise ValueError('hand_near_face_returns reference must be a nonnegative integer')
        observed = features.get('hand_near_face', {}).get('observed_returns')
        result['hand_near_face_returns'] = (
            {'status': 'insufficient_evidence'} if observed is None else
            {'observed': observed, 'reference': expected,
             'absolute_error': abs(observed - expected), 'exact_match': observed == expected}
        )
    for key in ('speaking_rate', 'pitch_variation'):
        if key in reference and features[key]['value'] is not None:
            result[key] = {'absolute_error': abs(features[key]['value'] - reference[key])}
    for key in ('prompt_coverage', 'organization'):
        if key in reference and features[key]['value'] is not None:
            result[key] = {'exact_match': features[key]['value'] == reference[key]}
    return result


def recording_event_metrics(rows, tolerance=0.25):
    """Score timestamped events across full recordings with a known duration."""
    if not rows:
        raise ValueError('provide at least one annotated recording')
    totals = dict(matches=0, predictions=0, references=0)
    seconds = error_sum = 0.0
    available_recordings = 0
    for row in rows:
        duration = row['duration_s']
        if not 0 < duration < float('inf'):
            raise ValueError('recording duration must be positive and finite')
        output = row['predicted']
        available_recordings += output is not None
        scores = event_scores(output if output is not None else [], row['reference'], tolerance)
        seconds += duration
        error_sum += (scores['mean_boundary_error_s'] or 0) * scores['matches']
        for name in totals:
            totals[name] += scores[name]
    matched, predicted, reference = (totals[k] for k in ('matches', 'predictions', 'references'))
    return {**totals, 'recordings': len(rows), 'duration_s': seconds,
            'available_recordings': available_recordings,
            'coverage': available_recordings / len(rows),
            'precision': matched / predicted if predicted else None,
            'recall': matched / reference if reference else None,
            'f1': 2 * matched / (predicted + reference) if predicted + reference else None,
            'false_alarms_per_minute': 60 * (predicted - matched) / seconds,
            'mean_boundary_error_s': error_sum / matched if matched else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis', type=Path)
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    print(json.dumps(score(json.loads(args.analysis.read_text())['features'],
                           json.loads(args.reference.read_text())), indent=2))

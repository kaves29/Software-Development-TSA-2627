"""Score every onboarding observation against independently labeled recordings."""

import argparse
import json
import math
from pathlib import Path
from statistics import mean

from .analysis import FEATURES
from .content import AREAS
from .evaluate import recording_event_metrics
from .video import NAMES

EVENTS = ('pauses', 'repetitions', 'revisions', 'um', 'uh', 'hand_near_face_intervals')
EXACT = (*AREAS, 'prompt_coverage', 'organization', 'hand_near_face_returns')
NUMERIC = tuple(name for name in (*FEATURES, *NAMES)
                if name not in (*EVENTS, *EXACT, 'fillers'))
TARGET = .50


def observation(features, name):
    source = ('fillers' if name in ('um', 'uh') else
              'hand_near_face' if name.startswith('hand_near_face_') else name)
    feature = features.get(source, {})
    if feature.get('status') in ('unavailable', 'insufficient_evidence'):
        return None
    if name == 'hand_near_face_intervals':
        return feature.get('intervals')
    if name == 'hand_near_face_returns':
        return feature.get('observed_returns')
    value = feature.get('value')
    if source == 'fillers' and value is not None:
        return [event for event in value if event.get('text') == name]
    return value


def numeric_error(actual, expected):
    if isinstance(expected, list):
        if not expected or not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError('numeric vectors must be nonempty and have matching lengths')
        return max(numeric_error(a, b) for a, b in zip(actual, expected))
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in (actual, expected)):
        raise ValueError('numeric values must be finite numbers')
    return abs(actual - expected)


def benchmark(recordings, tolerances):
    """Report one metric and label/prediction coverage per feature."""
    ids = [row['id'] for row in recordings]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('provide recordings with unique IDs')
    if any(not math.isfinite(row['duration_s']) or row['duration_s'] <= 0
           for row in recordings):
        raise ValueError('recording durations must be positive and finite')
    report = {}
    for name in (*EVENTS, *EXACT, *NUMERIC):
        labeled = [row for row in recordings if row['reference'].get(name) is not None]
        values = [observation(row['features'], name) for row in labeled]
        coverage = sum(value is not None for value in values)
        entry = {'score': None, 'status': 'missing_reference',
                 'speakers': len({row['speaker'] for row in labeled}),
                 'labeled_recordings': len(labeled), 'recordings': len(recordings),
                 'prediction_coverage': coverage / len(labeled) if labeled else None}
        report[name] = entry
        if not labeled:
            continue
        expected = [row['reference'][name] for row in labeled]
        if name in EVENTS:
            details = recording_event_metrics([
                {'duration_s': row['duration_s'], 'predicted': actual or [], 'reference': ref}
                for row, actual, ref in zip(labeled, values, expected)
            ])
            entry.update(details=details, score=details['f1'], metric='event_f1')
            if not details['references']:
                entry.update(score=None, status='no_positive_reference')
                continue
        elif name in EXACT:
            entry.update(score=mean(a is not None and a == b for a, b in zip(values, expected)),
                         metric='exact_agreement')
        else:
            if name not in tolerances:
                entry['status'] = 'missing_predeclared_tolerance'
                continue
            tolerance = tolerances[name]
            if not math.isfinite(tolerance) or tolerance < 0:
                raise ValueError(f'invalid tolerance for {name}')
            errors = [numeric_error(a, b) for a, b in zip(values, expected) if a is not None]
            entry.update(score=sum(error <= tolerance for error in errors) / len(labeled),
                         metric='within_tolerance_rate', tolerance=tolerance,
                         mean_recording_error=mean(errors) if errors else None)
        entry['status'] = 'meets_target' if entry['score'] >= TARGET else 'below_target'
    return {'target': TARGET, 'all_features_meet_target': all(
        row['status'] == 'meets_target' for row in report.values()), 'features': report}


def compare(manifest):
    """Compare frozen candidate and baseline predictions against identical labels."""
    recordings = manifest['recordings']
    development = set(manifest['development_speakers'])
    held_out = {row['speaker'] for row in recordings}
    if not development or development & held_out:
        raise ValueError('declare development speakers disjoint from held-out speakers')
    if any(not speaker for speaker in held_out | development):
        raise ValueError('speaker identifiers must be nonempty')
    tolerances = manifest['tolerances']
    baseline = benchmark([
        {**row, 'features': row['baseline_features']} for row in recordings
    ], tolerances)
    candidate = benchmark(recordings, tolerances)
    features = {}
    for name, result in candidate['features'].items():
        prior = baseline['features'][name]
        before, after = prior['score'], result['score']
        features[name] = {
            'baseline': prior, 'candidate': result,
            'change': None if before is None or after is None else after - before,
        }
    return {'target': TARGET, 'held_out_speakers': len(held_out),
            'all_features_meet_target': candidate['all_features_meet_target'],
            'features': features}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--compare', action='store_true', help='compare on held-out speakers')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = (compare(manifest) if args.compare else
              benchmark(manifest['recordings'], manifest['tolerances']))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

from speech_analysis.benchmark_features import benchmark


def test_benchmark_keeps_missing_labels_and_abstentions_visible():
    event = {'start_s': 1.0, 'end_s': 1.2, 'text': 'uh'}
    rows = [
        {'id': 'a', 'speaker': 'A', 'duration_s': 60,
         'features': {'fillers': {'value': [event]}, 'torso_sway': {'value': .12}},
         'reference': {'uh': [event], 'um': [], 'torso_sway': .10}},
        {'id': 'b', 'speaker': 'B', 'duration_s': 60, 'features': {},
         'reference': {'uh': [event], 'torso_sway': .10}},
    ]
    report = benchmark(rows, {'torso_sway': .03})
    features = report['features']
    assert len(features) == 35
    assert features['uh']['score'] == 2 / 3
    assert features['torso_sway']['score'] == .5
    assert features['torso_sway']['prediction_coverage'] == .5
    assert features['um']['status'] == 'no_positive_reference'
    assert features['shoulder_tilt']['status'] == 'missing_reference'
    assert not report['all_features_meet_target']


def test_event_matching_recovers_matches_that_greedy_matching_misses():
    from speech_analysis.evaluate import event_scores

    ref = [{'start_s': t, 'end_s': t + .1} for t in (0.72, 1.0)]
    pred = [{'start_s': t, 'end_s': t + .1} for t in (0.9, 1.13)]
    assert event_scores(pred, ref, .2)['matches'] == 2


def test_paired_comparison_uses_same_labels_and_rejects_development_overlap():
    import pytest
    from speech_analysis.benchmark_features import compare

    event = {'start_s': 1.0, 'end_s': 1.2, 'text': 'uh'}
    row = {'id': 'held-out', 'speaker': 'H', 'duration_s': 60,
           'baseline_features': {'fillers': {'value': []}},
           'features': {'fillers': {'value': [event]}},
           'reference': {'uh': [event]}}
    manifest = {'recordings': [row], 'development_speakers': ['D'], 'tolerances': {}}
    report = compare(manifest)
    assert report['features']['uh']['change'] == 1
    assert report['features']['um']['change'] is None
    assert not report['all_features_meet_target']
    with pytest.raises(ValueError, match='disjoint'):
        compare({**manifest, 'development_speakers': ['H']})

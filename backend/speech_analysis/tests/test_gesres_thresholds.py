import pytest

from speech_analysis.evaluate_gesres_thresholds import compare


def clip(label, value):
    return {'speed_label': label, 'rapid_motion': {'value': value}}


def test_threshold_selected_on_one_speaker_and_evaluated_on_another():
    train = {'video_id': 'one', 'fps': 10, 'results': [clip('fast', .8), clip('medium', .4), clip('fast', None)]}
    held = {'video_id': 'two', 'fps': 10, 'results': [clip('fast', .9), clip('medium', .5), clip('slow', None)]}
    report = compare(train, held)
    assert report['selected_threshold'] == .5
    assert report['development']['f1'] == 2 / 3
    assert report['evaluation']['f1'] == 2 / 3
    assert report['evaluation']['abstained'] == 1
    assert report['evaluation']['coverage'] == 2 / 3
    with pytest.raises(ValueError, match='distinct'):
        compare(train, {**held, 'video_id': 'one'})

import pytest

from speech_analysis.evaluate_gesres_hand import score


def row(label, left, right):
    return {'hand_label': label, 'left_hand_motion': {'value': left},
            'right_hand_motion': {'value': right}}


def test_one_handed_comparison_counts_abstentions_and_excludes_both():
    result = score([row('LH', .2, .1), row('RH', .2, .1), row('LH', None, .1),
                    row('RH', .1, .1), row('both', .3, .2)])
    assert result['labeled_clips'] == 4
    assert result['correct'] == 1
    assert result['coverage'] == .5
    assert result['accuracy_counting_abstentions_as_misses'] == .25
    assert result['accuracy_on_usable_clips'] == .5
    assert result['by_hand']['LH']['labeled'] == 2
    with pytest.raises(ValueError):
        score([row('LH', -.1, .2)])

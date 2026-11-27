from types import SimpleNamespace

import pytest

from speech_analysis.verbatim import analyze_timestamped_words


def word(text, start, end):
    return SimpleNamespace(word=text, start=start, end=end)


def test_verbatim_tags_preserve_filler_timestamps_and_exclude_nonwords():
    result = analyze_timestamped_words(6, [(0, 6)], [
        word('[UH],', 1, 1.3), word('[laughter]', 2, 2.5),
        word('we', 3, 3.2), word('we', 3.2, 3.4),
    ])
    assert result['fillers']['value'] == [{'text': 'uh', 'start_s': 1, 'end_s': 1.3}]
    assert result['repetitions']['value'][0]['end_s'] == 3.4
    assert result['speaking_rate']['value'] == 30


def test_verbatim_adapter_rejects_missing_timing():
    with pytest.raises(ValueError, match='timestamps'):
        analyze_timestamped_words(6, [(0, 6)], [word('[UM]', None, None)])


def test_verbatim_adapter_skips_collapsed_alignment_without_losing_valid_events():
    with pytest.warns(RuntimeWarning, match='1 zero-duration'):
        result = analyze_timestamped_words(100, [(0, 100)], [
            word('[UM]', 66.8, 66.8), word('[UH]', 67, 67.3),
        ])
    assert result['fillers']['value'] == [{'text': 'uh', 'start_s': 67, 'end_s': 67.3}]


def test_level_gate_discards_quiet_events_and_keeps_abstentions():
    import numpy as np

    from speech_analysis.verbatim import level_gated_fillers

    audio = np.concatenate([np.full(1000, .01), np.ones(1000)])
    quiet = {'text': 'uh', 'start_s': .2, 'end_s': .4}
    loud = {'text': 'um', 'start_s': 1.2, 'end_s': 1.4}
    assert level_gated_fillers([quiet, loud], audio, 1000) == [loud]
    assert level_gated_fillers(None, audio, 1000) is None


def test_repetition_candidate_keeps_chain_and_ignores_fillers_but_not_long_gaps():
    from speech_analysis.verbatim import repeat_events

    words = [('we', .1, .2), ('uh', .25, .35), ('we', .4, .5), ('we', .55, .65),
             ('can', .7, .8), ('can', 2., 2.1)]
    assert repeat_events(words) == [{'text': 'we we we', 'start_s': .1, 'end_s': .65}]


def test_retimed_gate_uses_label_duration_and_never_exceeds_recording():
    import numpy as np

    from speech_analysis.verbatim import retimed_level_gated_fillers

    events = [{'text': 'um', 'start_s': .1, 'end_s': .7},
              {'text': 'uh', 'start_s': .8, 'end_s': 1.0}]
    actual = retimed_level_gated_fillers(events, np.ones(1000), 1000)
    assert [event['start_s'] for event in actual] == [.1, .8]
    assert [event['end_s'] for event in actual] == [pytest.approx(.79), 1.0]

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

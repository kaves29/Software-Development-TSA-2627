from speech_analysis.filler_context import filter_filler_context


def test_context_rejects_unvoiced_and_ordinary_words_but_keeps_gaps_and_explicit_fillers():
    events = [{'text': 'uh', 'start_s': t, 'end_s': t + .25} for t in range(5)]
    words = [('another', 1, 1.3), ('Uh,', 2, 2.3), ('um', 4, 4.3)]
    assert filter_filler_context(events, words, [(1, 5)]) == [events[2], events[3]]

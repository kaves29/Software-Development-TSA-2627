"""Development-only comparison of timed fillers with voice activity."""


def filter_fillers_by_vad(events, speech):
    """Keep fillers at least half covered by speech; abstain if VAD unavailable."""
    if speech is None or not speech:
        return None
    spans = []
    for start, end in sorted(speech):
        if start >= end:
            raise ValueError('speech intervals must have positive duration')
        if spans and start <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], end))
        else:
            spans.append((start, end))
    kept = []
    for event in events:
        start, end = event['start_s'], event['end_s']
        if start >= end:
            raise ValueError('filler events must have positive duration')
        overlap = sum(max(0., min(end, b) - max(start, a)) for a, b in spans)
        if overlap >= (end - start) / 2:
            kept.append(event)
    return kept

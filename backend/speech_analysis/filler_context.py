"""Use transcript and voice activity to reject acoustic filler false alarms."""

import re


def filter_filler_context(events, words, speech):
    """Keep explicit fillers or voiced events mostly outside transcribed words."""
    tokens = [(re.sub(r'[^a-z]', '', text.lower()), start, end)
              for text, start, end in words if start < end]
    accepted = []
    for event in events:
        start, end = event['start_s'], event['end_s']
        midpoint = (start + end) / 2
        if not start < end or not any(a <= midpoint <= b for a, b in speech):
            continue
        overlaps = [(token, min(end, b) - max(start, a)) for token, a, b in tokens
                    if a < end and b > start]
        if any(token == event['text'] and overlap >= .5 * (end - start)
               for token, overlap in overlaps):
            accepted.append(event)
            continue
        if not any(token and overlap >= .5 * (end - start) for token, overlap in overlaps):
            accepted.append(event)
    return accepted

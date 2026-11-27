"""Convert timestamps from a verbatim ASR backend into Speakly observations."""

import math
import re

from .analysis import analyze_features

# Keep filler tags as spoken words, but never count nonlexical tags as words.
TAG = re.compile(r'\s*\[([^\[\]]+)\][.!?,;:]*\s*')


def analyze_timestamped_words(duration, speech, words, targets=()):
    """Use timed word objects from a backend such as CrisperWhisper."""
    normalized = []
    for word in words:
        text = word.word.strip()
        tag = TAG.fullmatch(text)
        if tag:
            text = tag[1].strip().lower()
            if text not in {'um', 'uh'}:
                continue
        start, end = word.start, word.end
        if (not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end))
                or not 0 <= start < end <= duration):
            raise ValueError(f'Invalid verbatim word timestamps: {start!r}, {end!r}')
        normalized.append((text, start, end))
    normalized.sort(key=lambda word: word[1])
    return analyze_features(duration, speech, normalized or None, targets)

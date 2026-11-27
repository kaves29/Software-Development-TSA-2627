"""Convert timestamps from a verbatim ASR backend into Speakly observations."""

import math
import re
import warnings

from .analysis import analyze_features

# Keep filler tags as spoken words, but never count nonlexical tags as words.
TAG = re.compile(r'\s*\[([^\[\]]+)\][.!?,;:]*\s*')


def analyze_timestamped_words(duration, speech, words, targets=()):
    """Use timed word objects from a backend such as CrisperWhisper."""
    normalized = []
    collapsed = 0
    for word in words:
        text = word.word.strip()
        tag = TAG.fullmatch(text)
        if tag:
            text = tag[1].strip().lower()
            if text not in {'um', 'uh'}:
                continue
        start, end = word.start, word.end
        if (not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end))
                or not 0 <= start <= end <= duration):
            raise ValueError(f'Invalid verbatim word timestamps: {start!r}, {end!r}')
        if start == end:
            collapsed += 1
            continue
        normalized.append((text, start, end))
    if collapsed:
        warnings.warn(f'Skipped {collapsed} zero-duration verbatim words', RuntimeWarning, stacklevel=2)
    normalized.sort(key=lambda word: word[1])
    return analyze_features(duration, speech, normalized or None, targets)


def level_gated_fillers(events, waveform, sample_rate):
    """Research filter for low-level detections on a close-miked track."""
    import numpy as np

    if events is None:
        return None
    window = sample_rate // 10
    frame_count = len(waveform) // window
    if not frame_count:
        return []
    frames = waveform[:frame_count * window].reshape(frame_count, window)
    cutoff = np.quantile(np.mean(frames ** 2, axis=1), .95) * 10 ** (-12 / 10)
    kept = []
    for event in events:
        start = round(event['start_s'] * sample_rate)
        end = round(event['end_s'] * sample_rate)
        clip = waveform[start:end]
        if len(clip) and np.mean(clip ** 2) >= cutoff:
            kept.append(event)
    return kept

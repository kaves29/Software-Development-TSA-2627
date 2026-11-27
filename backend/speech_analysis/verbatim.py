"""Convert timestamps from a verbatim ASR backend into Speakly observations."""

import math
import re
import warnings

from .analysis import TOKEN, analyze_features

# Keep filler tags as spoken words, but never count nonlexical tags as words.
TAG = re.compile(r'\s*\[([^\[\]]+)\][.!?,;:]*\s*')


def analyze_timestamped_words(duration, speech, words, targets=(), *, repetition_candidate=False):
    """Use timed word objects from a backend such as CrisperWhisper."""
    normalized = []
    collapsed = clamped = 0
    for word in words:
        text = word.word.strip()
        tag = TAG.fullmatch(text)
        if tag:
            text = tag[1].strip().lower()
            if text not in {'um', 'uh'}:
                continue
        start, end = word.start, word.end
        if (not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end))
                or not (0 <= start <= duration and start <= end <= duration + .01)):
            raise ValueError(f'Invalid verbatim word timestamps: {start!r}, {end!r}')
        if end > duration:
            clamped += 1
            end = duration
        if start == end:
            collapsed += 1
            continue
        normalized.append((text, start, end))
    if clamped:
        warnings.warn(f'Clamped {clamped} rounded word ends to the recording duration',
                      RuntimeWarning, stacklevel=2)
    if collapsed:
        warnings.warn(f'Skipped {collapsed} zero-duration verbatim words', RuntimeWarning, stacklevel=2)
    normalized.sort(key=lambda word: word[1])
    features = analyze_features(duration, speech, normalized or None, targets)
    if repetition_candidate and features['repetitions']['value'] is not None:
        features['repetitions']['research_candidate'] = repeat_events(normalized)
    return features


def repeat_events(words):
    """Find contiguous repetitions, ignoring fillers and merging repeated copies."""
    timed = [(token, start, end) for text, start, end in words
             for token in TOKEN.findall(text.lower().replace('’', "'")) if token not in {'um', 'uh'}]
    tokens = [token for token, _, _ in timed]
    events = []
    index = 0
    while index + 1 < len(tokens):
        for width in range(min(4, (len(tokens) - index) // 2), 0, -1):
            phrase = tokens[index:index + width]
            if (tokens[index + width:index + 2 * width] != phrase
                    or timed[index + width][1] - timed[index + width - 1][2] > .75):
                continue
            end = index + 2 * width
            while (tokens[end:end + width] == phrase
                   and timed[end][1] - timed[end - 1][2] <= .75):
                end += width
            events.append({'text': ' '.join(tokens[index:end]),
                           'start_s': timed[index][1], 'end_s': timed[end - 1][2]})
            index = end
            break
        else:
            index += 1
    return events


def level_gated_fillers(events, waveform, sample_rate, *, drop_db=12):
    """Research filter for low-level detections on a close-miked track."""
    import numpy as np

    if events is None:
        return None
    window = sample_rate // 10
    frame_count = len(waveform) // window
    if not frame_count:
        return []
    frames = waveform[:frame_count * window].reshape(frame_count, window)
    cutoff = np.quantile(np.mean(frames ** 2, axis=1), .95) * 10 ** (-drop_db / 10)
    kept = []
    for event in events:
        start = round(event['start_s'] * sample_rate)
        end = round(event['end_s'] * sample_rate)
        clip = waveform[start:end]
        if len(clip) and np.mean(clip ** 2) >= cutoff:
            kept.append(event)
    return kept

def retimed_level_gated_fillers(events, waveform, sample_rate):
    """Apply development-selected gates and AMI training-set median durations."""
    if events is None:
        return None
    duration = len(waveform) / sample_rate
    findings = []
    for label, drop_db, length in (('um', 8, .69), ('uh', 11, .33)):
        same_label = [event for event in events if event['text'] == label]
        accepted = level_gated_fillers(same_label, waveform, sample_rate, drop_db=drop_db)
        findings.extend({**event, 'end_s': min(duration, event['start_s'] + length)}
                        for event in accepted)
    return sorted(findings, key=lambda event: event['start_s'])

"""Decode contiguous filler events from frame probabilities."""

from .fillers import LABELS


def decode_frames(probabilities, duration, threshold=.6, min_frames=5):
    events = []
    start = 0
    active = 0
    scores = []
    for index, row in enumerate([*probabilities, [1, 0, 0]]):
        label = max(range(len(LABELS)), key=row.__getitem__)
        if row[label] < threshold:
            label = 0
        if label != active:
            if active and index - start >= min_frames:
                events.append({'text': LABELS[active], 'start_s': round(start * .02, 3),
                               'end_s': round(min(duration, index * .02), 3),
                               'score': round(sum(scores) / len(scores), 4)})
            start = index
            active = label
            scores = []
        if active:
            scores.append(row[active])
    return events


def score_recording(model, waveform, batch_size=16, *, window_samples=16000, device='cpu'):
    import numpy as np
    import torch

    stride = 320
    if window_samples < 640 or window_samples % 640:
        raise ValueError("window size must be a positive multiple of 640 samples")
    frame_count = (len(waveform) + stride - 1) // stride
    totals = np.zeros((frame_count, len(LABELS)))
    votes = np.zeros(frame_count)
    starts = list(range(0, len(waveform), window_samples // 2))
    model.eval()
    with torch.inference_mode():
        for index in range(0, len(starts), batch_size):
            batch = starts[index:index + batch_size]
            clips = [waveform[start:start + window_samples] for start in batch]
            audio = np.stack([np.pad(clip, (0, window_samples - len(clip))) for clip in clips])
            probabilities = model(torch.from_numpy(audio).to(device)).softmax(-1).cpu().numpy()
            for start, clip, rows in zip(batch, clips, probabilities):
                offset = start // stride
                valid = min(len(rows), max(0, (len(clip) - 400) // stride + 1))
                totals[offset:offset + valid] += rows[:valid]
                votes[offset:offset + valid] += 1
    totals[votes == 0, 0] = 1
    return totals / np.maximum(votes[:, None], 1)


def decode_hysteresis(probabilities, duration, *, onset, continuation, min_frames=5, max_gap=2):
    """Extend a confident filler through short dips in its frame scores."""
    if not 0 <= continuation <= onset <= 1 or min_frames < 1 or max_gap < 0:
        raise ValueError('invalid hysteresis parameters')
    candidates = []
    for label in (1, 2):
        start = last = None
        peak = 0.
        for index in range(len(probabilities) + max_gap + 1):
            score = probabilities[index][label] if index < len(probabilities) else -1.
            if score >= continuation:
                if start is None:
                    start = index
                last = index
                peak = max(peak, score)
            elif start is not None and index - last > max_gap:
                if peak >= onset and last + 1 - start >= min_frames:
                    candidates.append({'text': LABELS[label], 'start_s': round(start * .02, 3),
                                       'end_s': round(min(duration, (last + 1) * .02), 3),
                                       'score': round(float(peak), 4)})
                start = last = None
                peak = 0.
    selected = []
    for event in sorted(candidates, key=lambda item: -item['score']):
        if not any(event['start_s'] < prior['end_s'] and prior['start_s'] < event['end_s']
                   for prior in selected):
            selected.append(event)
    return sorted(selected, key=lambda item: item['start_s'])

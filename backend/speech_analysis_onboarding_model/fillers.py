"""Optional research classifier and fixed-window inference."""

import numpy as np
import torch
from torch import nn

LABELS = ('other', 'um', 'uh')
BASE_MODEL = 'facebook/wav2vec2-base'
BASE_REVISION = '0b5b8e868dd84f03fd87d01f9c4ff0f080fecfe8'
ENCODERS = {'wav2vec2': (BASE_MODEL, BASE_REVISION),
            'wavlm': ('microsoft/wavlm-base-plus', '4c66d4806a428f2e922ccfa1a962776e232d487b')}
RATE = 16000


class FillerClassifier(nn.Module):
    def __init__(self, encoder, unfreeze_last=0, encoder_name='wav2vec2'):
        super().__init__()
        if encoder_name not in ENCODERS:
            raise ValueError('unsupported encoder')
        self.encoder_name = encoder_name
        self.encoder = encoder.eval().requires_grad_(False)
        layers = encoder.encoder.layers
        if not 0 <= unfreeze_last <= len(layers):
            raise ValueError('invalid number of encoder layers to unfreeze')
        self.unfreeze_last = unfreeze_last
        if unfreeze_last:
            for layer in layers[-unfreeze_last:]:
                layer.requires_grad_(True)
        self.head = nn.Linear(encoder.config.hidden_size, len(LABELS))

    def forward(self, waveform):
        normalized = (waveform - waveform.mean(dim=-1, keepdim=True)) / (
            waveform.var(dim=-1, keepdim=True, unbiased=False) + 1e-7
        ).sqrt()
        if not self.unfreeze_last:
            self.encoder.eval()
        with torch.set_grad_enabled(self.training and bool(self.unfreeze_last)):
            hidden = self.encoder(normalized).last_hidden_state.mean(dim=1)
        return self.head(hidden)


def save_checkpoint(model, path):
    state = {'head': model.head.state_dict(), 'unfreeze_last': model.unfreeze_last,
             'encoder_name': model.encoder_name}
    if model.unfreeze_last:
        state['encoder'] = model.encoder.state_dict()
    torch.save(state, path)


def load_checkpoint(model, path):
    state = torch.load(path, map_location='cpu', weights_only=True)
    if state.get('kind') == 'frame_filler' and not getattr(model, 'frame_output', False):
        raise ValueError('frame checkpoint requires the frame classifier')
    if 'head' not in state:
        model.head.load_state_dict(state)
        return
    if state.get('encoder_name', 'wav2vec2') != model.encoder_name:
        raise ValueError('checkpoint encoder does not match model')
    model.head.load_state_dict(state['head'])
    if 'encoder' in state:
        model.encoder.load_state_dict(state['encoder'])


def checkpoint_encoder(path):
    state = torch.load(path, map_location='cpu', weights_only=True)
    name = state.get('encoder_name', 'wav2vec2')
    if name not in ENCODERS:
        raise ValueError('unsupported checkpoint encoder')
    return name


def score_filler_windows(model, waveform, speech):
    """Yield the winning filler class and score for candidate windows."""
    candidates = []
    for offset in range(0, len(waveform), RATE // 4):
        end = min(offset + RATE, len(waveform))
        midpoint = (offset + end) / (2 * RATE)
        if end - offset >= RATE // 2 and any(a <= midpoint <= b for a, b in speech):
            candidates.append((offset, end))

    model.eval()
    with torch.inference_mode():
        for i in range(0, len(candidates), 16):
            batch = candidates[i:i + 16]
            waveforms = np.stack([np.pad(waveform[a:b], (0, RATE - (b - a))) for a, b in batch])
            scores, classes = model(torch.from_numpy(waveforms)).softmax(-1).max(-1)
            for (a, b), score, label in zip(batch, scores.tolist(), classes.tolist()):
                if label:
                    yield {'text': LABELS[label], 'start_s': a / RATE, 'end_s': b / RATE,
                           'score': score}


def transcript_filler_candidates(words, speech, duration):
    """Generate explicit filler and speech-without-words candidates."""
    words = sorted((max(0, a), min(duration, b), text.strip().lower().strip('.,!?;:'))
                   for text, a, b in words if 0 <= a < b <= duration + .1)
    candidates = [(a, b, text) for a, b, text in words if text in LABELS[1:]]
    for start, end in speech:
        cursor = start
        for a, b, _ in words:
            if b <= start:
                continue
            if a >= end:
                break
            if .15 <= a - cursor <= 1.2:
                candidates.append((cursor, a, None))
            cursor = max(cursor, b)
        if .15 <= end - cursor <= 1.2:
            candidates.append((cursor, end, None))
    return sorted(candidates)


def score_transcript_fillers(model, waveform, words, speech):
    """Classify one-second windows centered on transcript and speech gaps."""
    candidates = transcript_filler_candidates(words, speech, len(waveform) / RATE)
    model.eval()
    with torch.inference_mode():
        for index in range(0, len(candidates), 16):
            batch = candidates[index:index + 16]
            clips = []
            for a, b, _ in batch:
                start = round((a + b - 1) * RATE / 2)
                end = start + RATE
                clips.append(np.pad(waveform[max(start, 0):end],
                                    (max(0, -start), max(0, end - len(waveform)))))
            scores, labels = model(torch.from_numpy(np.stack(clips))).softmax(-1).max(-1)
            for (a, b, explicit), score, label in zip(batch, scores.tolist(), labels.tolist()):
                if explicit or label:
                    yield {'text': explicit or LABELS[label], 'start_s': a, 'end_s': b,
                           'score': 1.0 if explicit else score}


def select_filler_events(windows, threshold):
    """Suppress overlapping proposals in timestamp order."""
    events = []
    for event in windows:
        if event['score'] < threshold:
            continue
        if events and event['start_s'] < events[-1]['end_s']:
            if event['score'] > events[-1]['score']:
                events[-1] = event
        else:
            events.append(event)
    return [{**event, 'score': round(event['score'], 4)} for event in events]


def detect_fillers(model, waveform, speech, threshold=0.85):
    return select_filler_events(score_filler_windows(model, waveform, speech), threshold)

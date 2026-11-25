"""Research-only clip classifier for two parsed annotation types."""

import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence


def collate(rows):
    waves, labels = zip(*rows)
    return pad_sequence(waves, batch_first=True), torch.tensor([len(x) for x in waves]), torch.stack(labels)


def annotation_scores(logits, targets):
    prediction = logits >= 0
    reference = targets.bool()
    result = {}
    for i, name in enumerate(('repetition', 'repair')):
        tp = int((prediction[:, i] & reference[:, i]).sum())
        fp = int((prediction[:, i] & ~reference[:, i]).sum())
        fn = int((~prediction[:, i] & reference[:, i]).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        result[name] = {'tp': tp, 'fp': fp, 'fn': fn, 'precision': precision, 'recall': recall,
                        'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    return result


def predict_segments(model, waveform, sample_rate=16000, window_seconds=12):
    """Return uncalibrated clip scores, not event detections or weaknesses."""
    output = []
    model.eval()
    size = sample_rate * window_seconds
    with torch.inference_mode():
        for start in range(0, len(waveform), size):
            segment = waveform[start:start + size]
            if len(segment) < sample_rate // 2:
                continue
            logits = model(segment.unsqueeze(0), torch.tensor([len(segment)], device=segment.device))
            probs = logits.sigmoid()[0].tolist()
            output.append({'start_s': start / sample_rate, 'end_s': (start + len(segment)) / sample_rate,
                           'probabilities': {'repetition': probs[0], 'repair': probs[1]}})
    return output


class DisfluencyClassifier(nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder.eval().requires_grad_(False)
        self.head = nn.Linear(encoder.config.hidden_size, 2)

    def forward(self, waveform, lengths):
        positions = torch.arange(waveform.shape[1], device=waveform.device)[None, :]
        mask = positions < lengths[:, None]
        values = waveform * mask
        mean = values.sum(-1, keepdim=True) / lengths[:, None]
        centered = (waveform - mean) * mask
        variance = centered.square().sum(-1, keepdim=True) / lengths[:, None]
        normalized = centered / (variance + 1e-7).sqrt()
        self.encoder.eval()
        with torch.no_grad():
            hidden = self.encoder(normalized, attention_mask=mask.long()).last_hidden_state
            frame_lengths = self.encoder._get_feat_extract_output_lengths(lengths).clamp(min=1, max=hidden.shape[1])
            frame_mask = torch.arange(hidden.shape[1], device=waveform.device)[None, :] < frame_lengths[:, None]
            pooled = (hidden * frame_mask.unsqueeze(-1)).sum(dim=1) / frame_lengths[:, None]
        return self.head(pooled)

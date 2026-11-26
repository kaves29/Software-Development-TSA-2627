"""Conservative parser for annotated reparandum/repair pairs in DisfluencySpeech."""

import re
import io

PAIR = re.compile(r'\[([^\[\]+]+)\+([^\[\]]+)\]')
WORDS = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)


def labeled_repairs(transcript):
    """Parse bracketed pairs; unmarked repairs are not negative examples."""
    events = []
    for match in PAIR.finditer(transcript):
        before = match.group(1).strip(' ,')
        after = match.group(2).strip(' ,')
        left = WORDS.findall(before.lower())
        right = WORDS.findall(after.lower())
        if not left or not right:
            continue
        repetition = len(right) >= len(left) and left == right[:len(left)] and not before.endswith('-')
        events.append({'type': 'repetition' if repetition else 'repair',
                       'reparandum': before, 'repair': after})
    return events


def clip_labels(transcript):
    """Predict presence of parsed annotation types, not clinical disfluency."""
    kinds = {event['type'] for event in labeled_repairs(transcript)}
    return (int('repetition' in kinds), int('repair' in kinds))


class DisfluencyClips:
    """Load short annotated full utterances; do not truncate clip-level labels."""

    def __init__(self, paths, limit=None, max_seconds=12):
        import pyarrow.parquet as pq
        import soundfile as sf

        self.rows = []
        for path in paths:
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=32, columns=['audio', 'transcript_annotated']):
                for row in batch.to_pylist():
                    payload = row['audio']['bytes']
                    info = sf.info(io.BytesIO(payload))
                    if info.channels != 1 or not 0.5 <= info.duration <= max_seconds:
                        continue
                    self.rows.append((payload, clip_labels(row['transcript_annotated'])))
                    if limit and len(self.rows) >= limit:
                        return
        if not self.rows:
            raise ValueError('no suitable disfluency utterances')

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        import librosa
        import numpy as np
        import soundfile as sf
        import torch

        payload, labels = self.rows[index]
        waveform, rate = sf.read(io.BytesIO(payload), dtype='float32')
        if rate != 16000:
            waveform = librosa.resample(waveform, orig_sr=rate, target_sr=16000)
        return torch.from_numpy(np.ascontiguousarray(waveform)), torch.tensor(labels, dtype=torch.float32)

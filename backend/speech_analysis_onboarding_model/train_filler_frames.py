"""Train a research frame head using the official PodcastFillers timestamp labels."""

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch.utils.data import DataLoader, Dataset, DistributedSampler
from transformers import AutoModel

from .fillers import ENCODERS, LABELS, RATE, FillerClassifier


def frame_targets(start, end, label, frame_count):
    # WavLM's convolutional extractor has a 400-sample receptive field
    # and produces one frame per 320 samples.
    centers = (torch.arange(frame_count) * 320 + 199.5) / RATE
    return ((centers >= start) & (centers < end)).long() * label


def continuous_targets(intervals, frame_count):
    centers = (torch.arange(frame_count) * 320 + 199.5) / RATE
    observed = torch.zeros((3, frame_count), dtype=torch.bool)
    for start, end, label in intervals:
        observed[label] |= (centers >= start) & (centers < end)
    labels = observed.long().argmax(dim=0)
    labels[observed.sum(dim=0) != 1] = -100
    return labels


class ContinuousWindows(Dataset):
    """Read four-second windows from predecoded mono 16 kHz episode WAVs."""

    samples = 4 * RATE
    frame_count = (samples - 400) // 320 + 1

    def __init__(self, episodes, csv_file, split, limit=None, *, window_hop_seconds=None):
        self.intervals = defaultdict(list)
        with csv_file.open(newline='', encoding='utf-8-sig') as source:
            for row in csv.DictReader(source):
                if row['clip_split_subset'].lower() != split or row['episode_split_subset'].lower() != split:
                    continue
                path = episodes / (row['podcast_filename'] + '.wav')
                label = row['label_consolidated_vocab'].lower()
                if label == 'none':
                    continue
                start = float(row['event_start_inepisode'])
                end = float(row['event_end_inepisode'])
                if 0 <= start < end:
                    self.intervals[path].append((start, end, LABELS.index(label) if label in LABELS else 0))
        if window_hop_seconds is not None and window_hop_seconds not in (1, 2, 4):
            raise ValueError('window hop must be 1, 2, or 4 seconds')
        self.windows = []
        for path, events in self.intervals.items():
            if not path.is_file():
                raise FileNotFoundError(path)
            for start, end, _ in events:
                offset = max(0, round(((start + end) / 2 - 2) * RATE))
                if window_hop_seconds is not None:
                    hop = window_hop_seconds * RATE
                    offset = (offset // hop) * hop
                self.windows.append((path, offset))
        self.windows = list(dict.fromkeys(self.windows))[:limit]
        if not self.windows:
            raise ValueError(f'empty {split} split')

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, index):
        path, offset = self.windows[index]
        with sf.SoundFile(path) as episode:
            if episode.samplerate != RATE or episode.channels != 1:
                raise ValueError('expected 16 kHz mono episodes')
            if offset >= len(episode):
                raise ValueError(f'annotation outside episode: {path}')
            episode.seek(offset)
            audio = episode.read(self.samples, dtype='float32')
        start = offset / RATE
        end = start + len(audio) / RATE
        intervals = [(left - start, min(right, end) - start, label)
                     for left, right, label in self.intervals[path] if right > start and left < end]
        labels = continuous_targets(intervals, self.frame_count)
        return torch.from_numpy(np.pad(audio, (0, self.samples - len(audio)))), labels


class AnnotatedClips(Dataset):
    def __init__(self, clips, csv_file, split, limit=None):
        with csv_file.open(newline='', encoding='utf-8-sig') as source:
            self.rows = [row for row in csv.DictReader(source)
                         if row['clip_split_subset'].lower() == split
                         and row['label_consolidated_vocab'].lower() != 'none']
        self.rows = self.rows[:limit]
        if not self.rows:
            raise ValueError(f'empty {split} split')
        self.clips = clips
        self.training = split == 'train'

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        audio, rate = sf.read(self.clips / row['clip_name'], dtype='float32')
        if rate != RATE or audio.ndim != 1:
            raise ValueError('expected 16 kHz mono clips')
        audio = np.pad(audio[:RATE], (0, max(0, RATE - len(audio))))
        label = row['label_consolidated_vocab'].lower()
        label = LABELS.index(label) if label in LABELS else 0
        start, end = (float(row[k]) for k in ('event_start_inclip', 'event_end_inclip'))
        shift = int(torch.randint(-1920, 1921, ()).item()) if self.training else 0
        if shift > 0:
            audio = np.pad(audio[:-shift], (shift, 0))
        elif shift < 0:
            audio = np.pad(audio[-shift:], (0, -shift))
        return torch.from_numpy(audio), start + shift / RATE, end + shift / RATE, label


class FrameClassifier(FillerClassifier):
    frame_output = True

    def forward(self, waveform):
        mean = waveform.mean(dim=-1, keepdim=True)
        scale = (waveform.var(dim=-1, keepdim=True, unbiased=False) + 1e-7).sqrt()
        self.encoder.eval()
        with torch.no_grad():
            frames = self.encoder((waveform - mean) / scale).last_hidden_state
        return self.head(frames)


def train(args):
    torch.manual_seed(42)
    torch.set_num_threads(4)
    world = int(os.getenv('WORLD_SIZE', '1'))
    rank = int(os.getenv('RANK', '0'))
    local_rank = int(os.getenv('LOCAL_RANK', '0'))
    device = torch.device(f'cuda:{local_rank}' if args.device == 'cuda' else args.device)
    if device.type == 'cuda':
        torch.cuda.set_device(device)
    if world > 1:
        torch.distributed.init_process_group('nccl' if device.type == 'cuda' else 'gloo')
    name, revision = ENCODERS['wavlm']
    encoder = (AutoModel.from_pretrained(args.model_dir, local_files_only=True) if args.model_dir
               else AutoModel.from_pretrained(name, revision=revision))
    model = FrameClassifier(encoder, encoder_name='wavlm').to(device)
    optimizer = torch.optim.AdamW(model.head.parameters(), lr=.001)
    dataset = ContinuousWindows if args.episodes else AnnotatedClips
    window_options = {} if args.window_hop_seconds is None else {'window_hop_seconds': args.window_hop_seconds}
    datasets = {split: dataset(args.episodes or args.clips, args.csv, split, args.limit, **window_options)
                for split in ('train', 'validation')}
    sampler = DistributedSampler(datasets['train']) if world > 1 else None
    loaders = {split: DataLoader(data, shuffle=split == 'train' and sampler is None,
                                 sampler=sampler if split == 'train' else None,
                                 batch_size=args.batch_size)
               for split, data in datasets.items()}
    wrapped = (torch.nn.parallel.DistributedDataParallel(
        model, device_ids=[local_rank] if device.type == 'cuda' else None)
        if world > 1 else model)
    best = -1
    for epoch in range(args.epochs):
        if sampler is not None:
            sampler.set_epoch(epoch)
        for split, loader in loaders.items():
            if split == 'validation' and rank != 0:
                continue
            training = split == 'train'
            model.train(training)
            matrix = torch.zeros((3, 3), dtype=torch.long)
            for audio, *annotations in loader:
                with torch.set_grad_enabled(training):
                    scores = (wrapped if training else model)(audio.to(device))
                    if args.episodes:
                        targets = annotations[0].to(device)
                    else:
                        targets = torch.stack([frame_targets(a, b, label, scores.shape[1])
                                               for a, b, label in zip(*annotations)]).to(device)
                    if training:
                        weights = scores.new_tensor([1., 3., 3.])
                        loss = torch.nn.functional.cross_entropy(
                            scores.flatten(0, 1), targets.flatten(), weight=weights, reduction='sum')
                        known = targets != -100
                        loss = loss / weights[targets[known]].sum().clamp_min(1)
                        optimizer.zero_grad(set_to_none=True)
                        loss.backward()
                        optimizer.step()
                known = targets != -100
                bins = 3 * targets[known] + scores.detach().argmax(-1)[known]
                matrix += torch.bincount(bins, minlength=9).reshape(3, 3).cpu()
            f1 = [2 * int(matrix[i, i]) / max(1, int(matrix[i].sum() + matrix[:, i].sum()))
                  for i in (1, 2)]
            if training and world > 1:
                device_matrix = matrix.to(device)
                torch.distributed.all_reduce(device_matrix)
                matrix = device_matrix.cpu()
                f1 = [2 * int(matrix[i, i]) / max(1, int(matrix[i].sum() + matrix[:, i].sum()))
                      for i in (1, 2)]
            if rank != 0:
                continue
            print(json.dumps({'epoch': epoch + 1, 'split': split, 'frames': matrix.tolist(),
                              'filler_mean_f1': sum(f1) / 2}), flush=True)
            if not training and sum(f1) / 2 > best:
                best = sum(f1) / 2
                args.output.parent.mkdir(parents=True, exist_ok=True)
                torch.save({'head': model.head.state_dict(), 'encoder_name': 'wavlm', 'revision': revision,
                            'kind': 'frame_filler', 'window_samples': ContinuousWindows.samples if args.episodes else RATE,
                            'validation_frame_f1': best}, args.output)
        if world > 1:
            torch.distributed.barrier()
    if world > 1:
        torch.distributed.destroy_process_group()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--clips', type=Path)
    source.add_argument('--episodes', type=Path)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--window-hop-seconds', type=int, choices=(1, 2, 4),
                        help='Snap annotation-centered windows to a fixed grid for continuous recordings')
    args = parser.parse_args()
    if args.window_hop_seconds is not None and not args.episodes:
        parser.error('--window-hop-seconds requires --episodes')
    train(args)

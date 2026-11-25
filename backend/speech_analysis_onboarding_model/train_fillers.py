"""Train a frozen wav2vec2 encoder's filler head on PodcastFillers clips."""

import argparse
import csv
import json
import os
import random
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch.nn.parallel import DistributedDataParallel
from torch.utils.data import DataLoader, Dataset, DistributedSampler
from transformers import AutoModel

from fillers import ENCODERS, LABELS, RATE, FillerClassifier, save_checkpoint, load_checkpoint, checkpoint_encoder


class PodcastClips(Dataset):
    def __init__(self, root, annotations, split, limit=None):
        paths = {}
        for path in root.rglob('*.wav'):
            if path.name in paths:
                raise ValueError(f'duplicate clip filename: {path.name}')
            paths[path.name] = path
        self.rows = []
        with annotations.open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                if row['clip_split_subset'].lower() != split:
                    continue
                label = row['label_consolidated_vocab'].strip().lower()
                if label == 'none':
                    continue
                self.rows.append((paths[row['clip_name']], LABELS.index(label) if label in LABELS else 0))
                if limit and len(self.rows) == limit:
                    break
        if not self.rows:
            raise ValueError(f'empty PodcastFillers split: {split}')

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        path, label = self.rows[index]
        waveform, rate = sf.read(path, dtype='float32')
        if rate != RATE or waveform.ndim != 1:
            raise ValueError(f'expected mono {RATE} Hz: {path}')
        return np.pad(waveform[:RATE], (0, max(0, RATE - len(waveform)))), label


def evaluate(model, clips, device, batch_size):
    matrix = torch.zeros(3, 3, dtype=torch.int64)
    model.eval()
    with torch.inference_mode():
        for audio, labels in DataLoader(clips, batch_size=batch_size):
            predictions = model(audio.to(device)).argmax(1).cpu()
            matrix += torch.bincount(3 * labels + predictions, minlength=9).reshape(3, 3)
    return score_matrix(matrix)


def score_matrix(matrix):
    scores = {}
    for i, label in enumerate(LABELS):
        tp = matrix[i, i].item()
        precision = tp / max(1, matrix[:, i].sum().item())
        recall = tp / max(1, matrix[i].sum().item())
        scores[label] = {'precision': precision, 'recall': recall,
                         'f1': 2 * precision * recall / max(1e-10, precision + recall)}
    return {'confusion_matrix': matrix.tolist(), 'labels': scores}


def compare_transcript_baseline(model, clips, device, limit):
    import whisper

    transcription = whisper.load_model('small.en', device=device, download_root=os.environ.get('SPEAKLY_MODEL_CACHE'))
    indices_by_label = [[i for i, (_, label) in enumerate(clips.rows) if label == index]
                        for index in range(len(LABELS))]
    rng = random.Random(42)
    matrices = [torch.zeros(3, 3, dtype=torch.int64) for _ in range(2)]
    with torch.inference_mode():
        for indices in indices_by_label:
            for i in rng.sample(indices, min(limit, len(indices))):
                audio, label = clips[i]
                transcript = transcription.transcribe(
                    audio, language='en', condition_on_previous_text=False,
                    temperature=0, fp16=device.type == 'cuda',
                )['text']
                match = re.search(r'\b(um|uh)\b', transcript.lower())
                baseline = LABELS.index(match.group()) if match else 0
                learned = model(torch.from_numpy(audio[None, :]).to(device)).argmax(1).item()
                matrices[0][label, baseline] += 1
                matrices[1][label, learned] += 1
    return {'whisper_transcript': score_matrix(matrices[0]),
            'wav2vec2_head': score_matrix(matrices[1])}


def train(args):
    rank = int(os.environ.get('RANK', 0))
    local_rank = int(os.environ.get('LOCAL_RANK', 0))
    world_size = int(os.environ.get('WORLD_SIZE', 1))
    device = torch.device('cpu' if args.cpu else f'cuda:{local_rank}')
    if not args.cpu:
        torch.cuda.set_device(device)
    if world_size > 1:
        torch.distributed.init_process_group('gloo' if args.cpu else 'nccl')
    try:
        torch.manual_seed(42)
        started = time.monotonic()
        split_names = (('test',) if args.evaluate_checkpoint else
                       ('train', 'validation') if args.validation_only else
                       ('train', 'validation', 'test'))
        splits = {split: PodcastClips(args.clips, args.csv, split, args.limit) for split in split_names}
        encoder_name = checkpoint_encoder(args.evaluate_checkpoint) if args.evaluate_checkpoint else args.encoder
        base_model, base_revision = ENCODERS[encoder_name]
        model = FillerClassifier(AutoModel.from_pretrained(base_model, revision=base_revision),
                                 unfreeze_last=args.unfreeze_last, encoder_name=encoder_name).to(device)
        if args.evaluate_checkpoint:
            if rank == 0:
                load_checkpoint(model, args.evaluate_checkpoint)
                result = {'checkpoint': str(args.evaluate_checkpoint), 'split_sizes': {'test': len(splits['test'])},
                          'test': evaluate(model, splits['test'], device, args.batch_size)}
                if args.baseline_per_label:
                    result['comparison'] = compare_transcript_baseline(model, splits['test'], device,
                                                                       args.baseline_per_label)
                args.output.mkdir(parents=True, exist_ok=True)
                (args.output / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
                print(json.dumps(result), flush=True)
            if world_size > 1:
                torch.distributed.barrier()
            return
        wrapped = DistributedDataParallel(model, device_ids=None if args.cpu else [local_rank]) if world_size > 1 else model
        sampler = DistributedSampler(splits['train'], seed=42) if world_size > 1 else None
        loader = DataLoader(splits['train'], batch_size=args.batch_size, sampler=sampler,
                            shuffle=sampler is None, num_workers=args.workers, pin_memory=not args.cpu)
        parameters = [{'params': model.head.parameters(), 'lr': 0.001}]
        if args.unfreeze_last:
            parameters.append({'params': [p for p in model.encoder.parameters() if p.requires_grad], 'lr': 0.00001})
        optimizer = torch.optim.AdamW(parameters)
        best_score = -1
        for epoch in range(args.epochs):
            if sampler:
                sampler.set_epoch(epoch)
            wrapped.train()
            for audio, targets in loader:
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=not args.cpu):
                    logits = wrapped(audio.to(device, non_blocking=True))
                    loss = torch.nn.functional.cross_entropy(
                        logits.float(), targets.to(device, non_blocking=True)
                    )
                loss.backward()
                optimizer.step()
            if rank == 0:
                validation = evaluate(model, splits['validation'], device, args.batch_size)
                score = sum(validation['labels'][label]['f1'] for label in ('um', 'uh')) / 2
                print(json.dumps({'epoch': epoch + 1, 'validation': validation}), flush=True)
                if score > best_score:
                    args.output.mkdir(parents=True, exist_ok=True)
                    save_checkpoint(model, args.output / 'filler-head.pt')
                    best_score = score
            if world_size > 1:
                torch.distributed.barrier()
        if rank == 0:
            load_checkpoint(model, args.output / 'filler-head.pt')
            result = {'base_model': base_model, 'base_revision': base_revision, 'world_size': world_size,
                      'devices': [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                      'duration_s': round(time.monotonic() - started, 2), 'unfreeze_last': args.unfreeze_last,
                      'split_sizes': {key: len(value) for key, value in splits.items()},
                      'best_validation_filler_f1': best_score}
            if not args.validation_only:
                result['test'] = evaluate(model, splits['test'], device, args.batch_size)
            if args.baseline_per_label and not args.validation_only:
                try:
                    result['comparison'] = compare_transcript_baseline(
                        model, splits['test'], device, args.baseline_per_label
                    )
                except (ImportError, OSError, RuntimeError, ValueError) as exc:
                    result['comparison_error'] = str(exc)
            (args.output / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result), flush=True)
    finally:
        if world_size > 1:
            torch.distributed.destroy_process_group()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clips', type=Path, required=True)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=24)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--baseline-per-label', type=int, default=0)
    parser.add_argument('--unfreeze-last', type=int, default=0, help='Unfreeze the last N encoder layers')
    parser.add_argument('--encoder', choices=tuple(ENCODERS), default='wav2vec2')
    parser.add_argument('--validation-only', action='store_true', help='Do not load or evaluate the test split')
    parser.add_argument('--evaluate-checkpoint', type=Path, help='Evaluate one selected checkpoint on the test split')
    parser.add_argument('--cpu', action='store_true')
    train(parser.parse_args())

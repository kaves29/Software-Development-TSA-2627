"""Research training for presence of parsed disfluency annotations per clip."""

import argparse
import json
import os
from pathlib import Path

import torch
from torch.nn.parallel import DistributedDataParallel
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler
from transformers import AutoModel

from .disfluency import DisfluencyClips
from .disfluency_model import DisfluencyClassifier, annotation_scores, collate
from .fillers import ENCODERS


def evaluate(model, data, device, batch_size):
    predictions, targets = [], []
    model.eval()
    with torch.inference_mode():
        for waves, lengths, labels in DataLoader(data, batch_size=batch_size, collate_fn=collate):
            predictions.append(model(waves.to(device), lengths.to(device)).cpu())
            targets.append(labels)
    return annotation_scores(torch.cat(predictions), torch.cat(targets))


def train(args):
    if {p.resolve() for p in args.train} & {p.resolve() for p in args.validation}:
        raise ValueError('train and validation paths must be distinct')
    rank = int(os.environ.get('RANK', '0'))
    local_rank = int(os.environ.get('LOCAL_RANK', '0'))
    world_size = int(os.environ.get('WORLD_SIZE', '1'))
    device = torch.device('cpu' if args.cpu else f'cuda:{local_rank}')
    if not args.cpu:
        torch.cuda.set_device(device)
    if world_size > 1:
        torch.distributed.init_process_group('gloo' if args.cpu else 'nccl')
    try:
        torch.manual_seed(42)
        train_data = DisfluencyClips(args.train, limit=args.limit)
        validation = DisfluencyClips(args.validation, limit=args.limit)
        model_name, revision = ENCODERS[args.encoder]
        model = DisfluencyClassifier(AutoModel.from_pretrained(model_name, revision=revision)).to(device)
        wrapped = DistributedDataParallel(model, device_ids=None if args.cpu else [local_rank]) if world_size > 1 else model
        sampler = DistributedSampler(train_data, seed=42) if world_size > 1 else None
        loader = DataLoader(train_data, batch_size=args.batch_size, sampler=sampler,
                            shuffle=sampler is None, collate_fn=collate)
        optimizer = torch.optim.AdamW(model.head.parameters(), lr=0.001)
        best = -1.0
        for epoch in range(args.epochs):
            if sampler:
                sampler.set_epoch(epoch)
            wrapped.train()
            for waves, lengths, labels in loader:
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=not args.cpu):
                    logits = wrapped(waves.to(device), lengths.to(device))
                    loss = torch.nn.functional.binary_cross_entropy_with_logits(logits.float(), labels.to(device))
                loss.backward()
                optimizer.step()
            if rank == 0:
                scores = evaluate(model, validation, device, args.batch_size)
                score = (scores['repetition']['f1'] + scores['repair']['f1']) / 2
                print(json.dumps({'epoch': epoch + 1, 'validation': scores}), flush=True)
                if score > best:
                    best = score
                    args.output.mkdir(parents=True, exist_ok=True)
                    torch.save({'head': model.head.state_dict(), 'encoder': args.encoder, 'revision': revision,
                                'label_semantics': 'presence of automatically parsed bracket annotation'},
                               args.output / 'disfluency-head.pt')
                    (args.output / 'metrics.json').write_text(json.dumps({
                        'validation': scores, 'best_validation_mean_f1': best,
                        'train_clips': len(train_data), 'validation_clips': len(validation),
                        'encoder': args.encoder, 'revision': revision, 'world_size': world_size,
                        'limitations': 'single acted speaker; labels are parsed annotation presence'}, indent=2) + '\n')
            if world_size > 1:
                torch.distributed.barrier()
    finally:
        if world_size > 1:
            torch.distributed.destroy_process_group()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', type=Path, nargs='+', required=True)
    parser.add_argument('--validation', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--encoder', choices=tuple(ENCODERS), default='wav2vec2')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=2)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--cpu', action='store_true')
    train(parser.parse_args())

"""Evaluate a selected research checkpoint on annotation-presence labels."""

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModel

from .disfluency import DisfluencyClips
from .disfluency_model import DisfluencyClassifier
from .fillers import ENCODERS
from .train_disfluency import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', nargs='+', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=2)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args()
    device = torch.device('cpu' if args.cpu else 'cuda:0')
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    base, revision = ENCODERS[checkpoint['encoder']]
    if checkpoint['revision'] != revision:
        raise ValueError('checkpoint revision mismatch')
    model = DisfluencyClassifier(AutoModel.from_pretrained(base, revision=revision)).to(device)
    model.head.load_state_dict(checkpoint['head'])
    dataset = DisfluencyClips(args.test, limit=args.limit)
    result = {'samples': len(dataset), 'test': evaluate(model, dataset, device, args.batch_size),
              'limitations': 'single acted speaker; targets are automatically parsed annotations'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

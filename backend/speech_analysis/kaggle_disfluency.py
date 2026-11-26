"""Stage pinned DisfluencySpeech data and run research training on two GPUs."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REVISION = 'b7da294fe3a70dd96df6640893f2a5dfc2c87638'
FILES = {
    'train-00000-of-00003.parquet': '6285da585435e76adefe43c3142852fd92a6be0c8c820486d941421a8638b4ae',
    'train-00001-of-00003.parquet': 'bfb907061b59e14fe9f9c2f6e9a00e13fe1cf531e50e6987c7cd34aecad81887',
    'train-00002-of-00003.parquet': '16bc5a61a9ff54923b78ca86d17c7028e5f36d9b3655637f3ffd64e73cf37426',
    'validation-00000-of-00001.parquet': '693ba2a06301d9cbafea52eae0664f8c776467e9b559ad9e25b6756f236f6a9c',
    'test-00000-of-00001.parquet': 'e78837be393206fc0ae6a0cefb4ec8c942c3e26401640eb8af67cf0dac21b4b0',
}


def stage(path, name, expected):
    target = path / name
    if not target.exists():
        temporary = target.with_suffix('.part')
        url = f'https://huggingface.co/datasets/amaai-lab/DisfluencySpeech/resolve/{REVISION}/data/{name}'
        subprocess.run(['curl', '-fL', '--retry', '4', '--connect-timeout', '30', '-o', str(temporary), url],
                       check=True)
        temporary.rename(target)
    with target.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError(f'dataset checksum mismatch: {name}')
    return target


def run(root):
    import torch

    devices = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    if len(devices) != 2 or any('T4' not in name for name in devices):
        raise RuntimeError('expected two T4 GPUs')
    data = root / 'disfluency-data'
    data.mkdir(exist_ok=True)
    paths = {name: stage(data, name, checksum) for name, checksum in FILES.items()}
    output = Path('/kaggle/working/disfluency-research')
    env = dict(os.environ, PYTHONPATH=str(root), OMP_NUM_THREADS='2')
    train = [str(path) for name, path in paths.items() if name.startswith('train-')]
    validation = next(path for name, path in paths.items() if name.startswith('validation-'))
    test = next(path for name, path in paths.items() if name.startswith('test-'))
    subprocess.run([sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc-per-node=2',
                    '-m', 'speech_analysis.train_disfluency', '--train', *train,
                    '--validation', str(validation), '--output', str(output), '--batch-size', '2'],
                   check=True, env=env)
    subprocess.run([sys.executable, '-m', 'speech_analysis.evaluate_disfluency', '--test', str(test),
                    '--checkpoint', str(output / 'disfluency-head.pt'), '--output', str(output / 'test.json')],
                   check=True, env=env)
    (output / 'run.json').write_text(json.dumps({'devices': devices, 'dataset_revision': REVISION}, indent=2))

"""Prepare the official research data and launch the private Kaggle run."""

import csv
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

RECORD = 'https://zenodo.org/records/7121457/files'
FILES = {
    'PodcastFillers.zip': '20e9f6b93b1b5c2e1c9d8b774ca28c33',
    'PodcastFillers.csv': '68d8614ad562263c621b90dc81f06abd',
}


def download(root, name, checksum):
    path = root / name
    if not path.exists():
        partial = path.with_suffix(path.suffix + '.part')
        subprocess.run(['curl', '-fL', '--retry', '4', '--retry-all-errors', '--connect-timeout', '30',
                        '-C', '-', '-o', str(partial), f'{RECORD}/{name}'], check=True)
        partial.rename(path)
    try:
        verify_archive(path, checksum)
    except ValueError:
        path.unlink()
        raise
    return path


def verify_archive(path, checksum):
    with path.open('rb') as stream:
        observed = hashlib.file_digest(stream, 'md5').hexdigest()
    if observed != checksum:
        raise ValueError(f'checksum mismatch: {path.name}')


def skip_episode_volumes(root, size=6442450944, count=3):
    # The pinned release stores every numbered clip entirely on the final volume.
    # 7-Zip needs the other volumes' sizes for offsets even when reading only clips.
    for index in range(1, count + 1):
        path = root / f'PodcastFillers.z{index:02}'
        if not path.exists():
            with path.open('xb') as volume:
                if index == 1:
                    volume.write(b'PK\x07\x08')
                volume.truncate(size)


def verify_clip_names(clips, csv_path):
    with csv_path.open(newline='', encoding='utf-8-sig') as stream:
        expected = {row['clip_name'] for row in csv.DictReader(stream)}
    observed = {path.name for path in clips.glob('*.wav')}
    if not expected or expected != observed:
        raise ValueError(f'clip inventory mismatch: {len(expected - observed)} missing, '
                         f'{len(observed - expected)} unexpected')


def extract_clips(root, sevenzip):
    clips = root / 'clips'
    clips.mkdir(exist_ok=True)
    subprocess.run([str(sevenzip), 'e', str(root / 'PodcastFillers.zip'), '-r',
                    '?????.wav', f'-o{clips}', '-aos', '-bsp0'], check=True)
    return clips


EPISODE_VOLUME_CHECKSUM = '399c44abb9ec35aa56d6fbf75043164b'


def extract_episodes(root, sevenzip, csv_path):
    members = {}
    with csv_path.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            split = row['clip_split_subset']
            if split in ('train', 'validation') and row['episode_split_subset'] == split:
                name = row['podcast_filename']
                members[name] = f'PodcastFillers/audio/episode_mp3/{split}/{name}.mp3'
    include = root / 'episode-members.txt'
    include.write_text(''.join(member + '\n' for member in sorted(members.values())), encoding='utf-8')
    episodes = root / 'episodes'
    episodes.mkdir(exist_ok=True)
    subprocess.run([str(sevenzip), 'e', str(root / 'PodcastFillers.zip'),
                    f'-i@{include}', '-scsUTF-8', '-spd', f'-o{episodes}', '-aoa', '-bsp0'], check=True)
    observed = {path.stem for path in episodes.glob('*.mp3')}
    if not members or observed != members.keys():
        raise ValueError('original episode inventory differs from the official training and validation splits')
    for name in sorted(members):
        audio = episodes / f'{name}.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(audio),
                        '-ac', '1', '-ar', '16000', str(audio.with_suffix('.wav'))], check=True)
        audio.unlink()
    return episodes


def install_extractor(root):
    archive = root / '7zip.tar.xz'
    subprocess.run(['curl', '-fL', '--retry', '4', '-o', str(archive),
                    'https://github.com/ip7z/7zip/releases/download/25.01/7z2501-linux-x64.tar.xz'],
                   check=True)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != '4ca3b7c6f2f67866b92622818b58233dc70367be2f36b498eb0bdeaaa44b53f4':
        raise ValueError('7-Zip release checksum mismatch')
    with tarfile.open(archive) as release:
        binary = root / '7zz'
        binary.write_bytes(release.extractfile('7zz').read())
        binary.chmod(0o700)
    return binary


def select_candidate(root):
    candidates = ('frozen', 'partial', 'wavlm')
    scores = {name: json.loads((root / name / 'metrics.json').read_text())['best_validation_filler_f1']
              for name in candidates}
    return max(candidates, key=lambda name: scores[name])


def run(root, frames_only=False, continuous=False):
    import os

    import torch

    print(json.dumps({'gpus': [torch.cuda.get_device_name(i)
                              for i in range(torch.cuda.device_count())]}), flush=True)
    if torch.cuda.device_count() != 2 or any('T4' not in torch.cuda.get_device_name(i)
                                            for i in range(2)):
        raise RuntimeError('Kaggle did not allocate two T4 GPUs')
    data = root / 'data'
    data.mkdir(exist_ok=True)
    bundle_dir = os.getenv('SPEAKLY_CONTINUOUS_INPUT') if continuous else None
    bundle = Path(bundle_dir) if bundle_dir else None
    required = {**FILES, 'PodcastFillers.z03': EPISODE_VOLUME_CHECKSUM} if continuous else FILES
    if bundle:
        for name, checksum in required.items():
            source_file = bundle / name
            verify_archive(source_file, checksum)
            staged = data / name
            if staged.resolve() != source_file.resolve():
                staged.unlink(missing_ok=True)
                staged.symlink_to(source_file)
        sevenzip = bundle / '7zz'
        sevenzip_copy = root / '7zz'
        binary = sevenzip.read_bytes()
        if hashlib.sha256(binary).hexdigest() != 'a1860fdf0d6ec395e0e277e5222e9aa488747db4aa5c87d1ec879a0916ba0b2f':
            raise ValueError('7-Zip binary checksum mismatch')
        sevenzip_copy.write_bytes(binary)
        sevenzip_copy.chmod(0o700)
        sevenzip = sevenzip_copy
    else:
        for name, checksum in required.items():
            download(data, name, checksum)
        sevenzip = install_extractor(root)
    skip_episode_volumes(data)
    csv_path = data / 'PodcastFillers.csv'
    if continuous:
        episodes = extract_episodes(data, sevenzip, csv_path)
    else:
        clips = extract_clips(data, sevenzip)
        verify_clip_names(clips, csv_path)
    if frames_only or continuous:
        source = ['--episodes', str(episodes)] if continuous else ['--clips', str(clips)]
        if bundle:
            source += ['--model-dir', str(bundle / 'wavlm')]
        checkpoint = 'filler-continuous-head.pt' if continuous else 'filler-frame-head.pt'
        subprocess.run([sys.executable, '-m', 'torch.distributed.run', '--standalone',
                        '--nproc-per-node=2', '-m', 'speech_analysis.train_filler_frames',
                        *source, '--csv', str(csv_path), '--output', f'/kaggle/working/{checkpoint}',
                        '--batch-size', '8' if continuous else '32', '--device', 'cuda'],
                       check=True, env={**os.environ, 'PYTHONPATH': str(root)})
        return
    output = Path('/kaggle/working/filler-comparison')
    for name, unfreeze, encoder in (('frozen', 0, 'wav2vec2'), ('partial', 1, 'wav2vec2'),
                                    ('wavlm', 0, 'wavlm')):
        subprocess.run([sys.executable, '-m', 'torch.distributed.run', '--standalone',
                        '--nproc-per-node=2', str(root / 'train_fillers.py'), '--clips', str(clips),
                        '--csv', str(data / 'PodcastFillers.csv'), '--output', str(output / name),
                        '--unfreeze-last', str(unfreeze), '--encoder', encoder, '--validation-only'], check=True)
    selected = select_candidate(output)
    (output / 'selected.json').write_text(json.dumps({'selected': selected, 'criterion': 'validation filler mean F1'}))
    subprocess.run([sys.executable, str(root / 'train_fillers.py'), '--clips', str(clips),
                    '--csv', str(data / 'PodcastFillers.csv'), '--output', str(output / 'test'),
                    '--evaluate-checkpoint', str(output / selected / 'filler-head.pt'),
                    '--baseline-per-label', '32'], check=True)
    sys.path.insert(0, str(root))
    from speech_analysis.kaggle_disfluency import run as run_disfluency
    run_disfluency(root)


def notebook(owner, destination, frames_only=False, continuous=False):
    source = Path(__file__).parent
    files = {name: (source / name).read_text() for name in
             ('fillers.py', 'train_fillers.py', 'kaggle_job.py')}
    files.update({f'speech_analysis/{name}': (source / name).read_text() for name in
                  ('fillers.py', 'disfluency.py', 'disfluency_model.py', 'train_disfluency.py',
                   'evaluate_disfluency.py', 'kaggle_disfluency.py', 'train_filler_frames.py')})
    command = "run-continuous" if continuous else "run-frames" if frames_only else "run"
    dependencies = ["transformers==4.57.6", "soundfile"]
    if not (continuous or frames_only):
        dependencies += ["openai-whisper==20250625", "pyarrow==22.0.0", "librosa==1.0.1"]
    network_check = (
        'import importlib.metadata, socket, time\n'
        'def wait_for_dns(host):\n'
        '    for delay in (0, 15, 30, 60):\n'
        '        time.sleep(delay)\n'
        '        try:\n'
        '            socket.getaddrinfo(host, 443)\n'
        '            return\n'
        '        except socket.gaierror as error:\n'
        '            print(f"Kaggle DNS lookup failed for {host}: {error}", flush=True)\n'
        '    raise RuntimeError(f"Kaggle worker cannot resolve {host} after retries. Check Internet is On, then retry on a fresh worker.")\n'
        'def missing(requirement):\n'
        '    package, _, version = requirement.partition("==")\n'
        '    try:\n'
        '        installed = importlib.metadata.version(package)\n'
        '    except importlib.metadata.PackageNotFoundError:\n'
        '        return True\n'
        '    return bool(version and installed != version)\n'
        'import os\n'
        f'bundles = list(Path("/kaggle/input").glob("**/speakly-continuous-input.json")) if {continuous!r} else []\n'
        'if len(bundles) > 1:\n'
        '    raise RuntimeError("Attach only one Speakly continuous input bundle.")\n'
        'if bundles:\n'
        '    bundle = bundles[0].parent\n'
        '    os.environ["SPEAKLY_CONTINUOUS_INPUT"] = str(bundle)\n'
        'for host in (() if bundles else ("zenodo.org", "huggingface.co")):\n'
        '    wait_for_dns(host)\n'
        f'needed = [requirement for requirement in {dependencies!r} if missing(requirement)]\n'
        'if needed:\n'
        '    if bundles:\n'
        '        pip_source = ["--no-index", "--find-links", str(bundle / "wheels")]\n'
        '    else:\n'
        '        wait_for_dns("pypi.org")\n'
        '        pip_source = []\n'
        '    subprocess.run([sys.executable, "-m", "pip", "install", *pip_source, *needed], check=True)\n'
    )
    code = (
        'import subprocess, sys\nfrom pathlib import Path\n'
        'root = Path("/kaggle/temp/speakly")\nroot.mkdir(parents=True, exist_ok=True)\n'
        f'files = {files!r}\n'
        'for name, content in files.items():\n    path = root / name\n    path.parent.mkdir(parents=True, exist_ok=True)\n    path.write_text(content)\n'
        + network_check
        + f'subprocess.run([sys.executable, str(root / "kaggle_job.py"), {command!r}], check=True)\n'
    )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'train.ipynb').write_text(json.dumps({
        'cells': [{'cell_type': 'code', 'source': code, 'metadata': {}, 'outputs': [],
                   'execution_count': None}],
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'nbformat': 4, 'nbformat_minor': 4,
    }))
    slug = 'speakly-filler-frames' if frames_only else 'speakly-filler-research'
    title = 'Speakly Filler Frames' if frames_only else 'Speakly Filler Research'
    if continuous:
        slug, title = 'speakly-filler-continuous', 'Speakly Filler Continuous'
    (destination / 'kernel-metadata.json').write_text(json.dumps({
        'id': f'{owner}/{slug}', 'title': title,
        'code_file': 'train.ipynb', 'language': 'python', 'kernel_type': 'notebook',
        'is_private': True, 'enable_gpu': True, 'enable_internet': True,
        'dataset_sources': [], 'competition_sources': [], 'kernel_sources': [],
    }))


if __name__ == '__main__':
    if sys.argv[1:] in (['run'], ['run-frames'], ['run-continuous']):
        run(Path(__file__).parent, frames_only=sys.argv[1] == 'run-frames', continuous=sys.argv[1] == 'run-continuous')
    elif len(sys.argv) == 4 and sys.argv[1] == '--frames':
        notebook(sys.argv[2], Path(sys.argv[3]), frames_only=True)
    elif len(sys.argv) == 4 and sys.argv[1] == '--continuous':
        notebook(sys.argv[2], Path(sys.argv[3]), continuous=True)
    elif len(sys.argv) == 3:
        notebook(sys.argv[1], Path(sys.argv[2]))
    else:
        raise SystemExit('Usage: python kaggle_job.py KAGGLE_OWNER OUTPUT_DIRECTORY')

"""Generate a private, manually queued AMI adaptation notebook."""

import argparse
import json
from pathlib import Path

ANNOTATIONS = (
    "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip"
)
ANNOTATIONS_SHA = "b56e5babb2496b8795deeeda7e71178d7fbc9963f94276cf2a3f4b56ebbc9f9d"
CHECKPOINT_SHA = "68aee44b596e7a36c46f5c1aaa083b4dfb0c46aa1cd4540872cc211484f19ca4"
TRAIN = (
    "ES2008a.A",
    "TS3005a.A",
    "ES2005a.A",
    "ES2006a.A",
    "TS3009a.A",
    "IS1003a.A",
    "ES2002a.A",
    "ES2007a.A",
    "ES2010a.A",
    "TS3011a.A",
)
DEVELOPMENT = ("IS1008a.D", "TS3004a.A")
AUDIO_SHA = {
    "ES2008a.A": "9038704a0c2380b3abed17af3927e110a3783d3e8a0a7743af86275552f5588a",
    "TS3005a.A": "7ca6fe56d9a8b2294ff69a13466ebce1c408434f2f457a245eec792b5fa266f9",
    "ES2005a.A": "ffe5eb825fcc0a9113173d828c1ce66e256e49c6e933987927c6353043ef4112",
    "ES2006a.A": "2ee7c31443367833a385d1bd8c56b6a516a56193b90892fb042e9ad681109b18",
    "TS3009a.A": "7b789a7109a59b54e033f82ed1a7a91881114b84bae7ffa1f4692d650b31c5ae",
    "IS1003a.A": "5a633e76470335e5e7d830980f00269f1dee28ceecf38a07257b1b7c1e5bd8d6",
    "ES2002a.A": "3bf0627106d6b6f02e5cc8b69f283b70303275c6b354aef3bdc7a50762d3f25e",
    "ES2007a.A": "869ffbca7c16ea0e8093388aaed0383d03480deddb0a1cdf4f9bb081bc4cfa61",
    "ES2010a.A": "d2b9737be13bcb49f8ec5fd8f55884edf6326864fde1098e4fb244675e9cebec",
    "TS3011a.A": "f46b3f9fb8e4945e50fa46bc7ae29a3601d624c8d7f652af7725d900aefd8493",
    "IS1008a.D": "a60e45356e8324231ba259bc63046d68aefc17b4a063a6a497736e7cb525642a",
    "TS3004a.A": "bde78c71e744b535f860964160857b646c3052c1286a4fb2c015fccf8991dcf0",
}
MODULES = (
    "__main__",
    "acoustics",
    "analysis",
    "ami_split",
    "ami_training",
    "adapt_ami_filler",
    "evaluate",
    "evaluate_ami",
    "filler_frames",
    "fillers",
    "train_filler_frames",
)


def notebook(destination):
    package = Path(__file__).parent
    sources = {f"{name}.py": (package / f"{name}.py").read_text() for name in MODULES}
    setup = f"""from pathlib import Path
import hashlib
import subprocess
import sys
from zipfile import ZipFile

root = Path('/kaggle/temp/speakly-ami')
root.mkdir(parents=True, exist_ok=True)
package = root / {package.name!r}
package.mkdir(exist_ok=True)
for name, source in {sources!r}.items():
    (package / name).write_text(source)
sys.path.insert(0, str(root))
from {package.name}.ami_split import recording_splits
"""
    prepare = f"""def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def download(url, path):
    if not path.exists():
        partial = path.with_suffix('.part')
        subprocess.run(['curl', '-fLsS', '--retry', '4', '--retry-all-errors',
                        '--connect-timeout', '20', '--max-time', '180',
                        '-o', str(partial), url], check=True)
        partial.replace(path)

checkpoints = list(Path('/kaggle/input').rglob('filler-continuous-head.pt'))
if len(checkpoints) != 1 or digest(checkpoints[0]) != {CHECKPOINT_SHA!r}:
    raise ValueError('Attach exactly one verified filler-continuous-head.pt as a private Kaggle input.')

annotations = root / 'ami_public_manual_1.6.2.zip'
download({ANNOTATIONS!r}, annotations)
if digest(annotations) != {ANNOTATIONS_SHA!r}:
    raise ValueError('AMI annotation archive checksum mismatch')
with ZipFile(annotations) as archive:
    splits = recording_splits(archive)
train, development = {TRAIN!r}, {DEVELOPMENT!r}
audio = root / 'audio'
audio.mkdir(exist_ok=True)
for split, requested in (('training', train), ('development', development)):
    entries = {{row['recording']: row for row in splits[split]}}
    for recording in requested:
        channel = entries[recording]['headset_channel']
        meeting = recording.split('.')[0]
        url = ('https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/'
               f'{{meeting}}/audio/{{meeting}}.Headset-{{channel}}.wav')
        path = audio / f'{{recording}}.wav'
        download(url, path)
        if digest(path) != {AUDIO_SHA!r}[recording]:
            raise ValueError(f'AMI audio checksum mismatch: {{recording}}')
        subprocess.run(['ffprobe', '-v', 'error', str(path)], check=True)
"""
    run = f"""subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                'transformers==4.57.6', 'soundfile==0.14.0'], check=True)
output = root / 'adaptation'
command = [sys.executable, '-m', '{package.name}.adapt_ami_filler',
           str(annotations), str(audio), str(checkpoints[0]), str(output),
           '--windows-per-track', '120', '--device', 'cuda']
for recording in train:
    command.extend(['--train', recording])
for recording in development:
    command.extend(['--development', recording])
subprocess.run(command, cwd=root, check=True)
import shutil
result = Path('/kaggle/working/speakly-ami-results')
result.mkdir(exist_ok=True)
for name in ('metrics.json', 'inputs.json', 'head.pt'):
    shutil.copy2(output / name, result / name)
"""
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "Private Speakly experiment. Attach the verified filler head as a private input, "
            "enable a GPU and internet, then run all cells. This notebook reads only AMI train "
            "and development labels. It copies metrics and the experimental head to outputs.",
        }
    ]
    cells.extend(
        {
            "cell_type": "code",
            "metadata": {},
            "source": cell,
            "outputs": [],
            "execution_count": None,
        }
        for cell in (setup, prepare, run)
    )
    destination.write_text(
        json.dumps(
            {
                "cells": cells,
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 4,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    notebook(parser.parse_args().output)

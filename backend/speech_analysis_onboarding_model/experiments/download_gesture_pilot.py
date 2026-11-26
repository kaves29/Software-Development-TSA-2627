"""Download the public, noncommercial gesture pilot samples listed in the manifest.

Requires remotezip. Review the dataset's CC BY-NC-SA 4.0 terms before use.
"""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from remotezip import RemoteZip

ARCHIVE = "https://zenodo.org/api/records/22638749/files/gesture_challenge_2026_release_v1_train.zip/content"


def download_group(samples, directory):
    with RemoteZip(ARCHIVE) as archive:
        for sample in samples:
            target = directory / Path(sample["path"]).name
            if (
                target.exists()
                and hashlib.sha256(target.read_bytes()).hexdigest() == sample["sha256"]
            ):
                continue
            payload = archive.read(sample["path"])
            if hashlib.sha256(payload).hexdigest() != sample["sha256"]:
                raise ValueError(f"Checksum mismatch: {target.name}")
            target.write_bytes(payload)
            print(target.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        Path(__file__).with_name("gesture_pilot_manifest.json").read_text()
    )
    samples = manifest["samples"]
    metadata = args.directory / "metadata_summary.csv"
    if (
        not metadata.exists()
        or hashlib.md5(metadata.read_bytes()).hexdigest() != manifest["metadata_md5"]
    ):
        with urlopen(
            "https://zenodo.org/api/records/22638749/files/metadata_summary.csv/content",
            timeout=60,
        ) as response:
            payload = response.read()
        if hashlib.md5(payload).hexdigest() != manifest["metadata_md5"]:
            raise ValueError("Metadata checksum mismatch")
        metadata.write_bytes(payload)
    if len({Path(x["path"]).name for x in samples}) != len(samples):
        raise ValueError("Duplicate file names in manifest")
    samples = [
        sample
        for sample in samples
        if not (args.directory / Path(sample["path"]).name).exists()
        or hashlib.sha256(
            (args.directory / Path(sample["path"]).name).read_bytes()
        ).hexdigest()
        != sample["sha256"]
    ]
    if not samples:
        print("All manifest samples are present and verified.")
        return
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(
            pool.map(
                lambda group: download_group(group, args.directory),
                [samples[i::5] for i in range(5)],
            )
        )


if __name__ == "__main__":
    main()

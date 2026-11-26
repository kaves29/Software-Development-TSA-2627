"""Download the public, noncommercial gesture pilot samples listed in the manifest.

Requires remotezip. Review the dataset's CC BY-NC-SA 4.0 terms before use.
"""

import argparse
import hashlib
import json
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
    parser.add_argument(
        "--expanded", action="store_true", help="Include extra TED training clips"
    )
    parser.add_argument(
        "--multisimo",
        action="store_true",
        help="Include domain training and the MULTISIMO development clips",
    )
    parser.add_argument(
        "--additional-speakers",
        action="store_true",
        help="Include four additional MULTISIMO speakers",
    )
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(
        Path(__file__).with_name("gesture_pilot_manifest.json").read_text()
    )
    samples = manifest["samples"]
    if args.expanded or args.multisimo or args.additional_speakers:
        by_name = {Path(sample["path"]).name: sample for sample in samples}
        manifests = ["gesture_domain_manifest.json"]
        if args.multisimo or args.additional_speakers:
            manifests.append("gesture_multisimo_manifest.json")
        if args.additional_speakers:
            manifests.append("gesture_multisimo_extra_manifest.json")
        for manifest_name in manifests:
            expanded = json.loads(Path(__file__).with_name(manifest_name).read_text())
            for sample in expanded["samples"]:
                name = Path(sample["path"]).name
                if name in by_name and sample["sha256"] != by_name[name]["sha256"]:
                    raise ValueError(f"Conflicting sample hash: {name}")
                by_name[name] = sample
        samples = list(by_name.values())
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
    # The source has a rate limit; avoid concurrent range requests.
    download_group(samples, args.directory)


if __name__ == "__main__":
    main()

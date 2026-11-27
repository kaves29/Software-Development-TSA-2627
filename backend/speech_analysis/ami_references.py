"""Build independent filler and rate references from AMI manual word timing."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .analysis import TOKEN


def word_references(archive, recording, duration):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('provide the complete recording duration in seconds')
    with archive.open(f'words/{recording}.words.xml') as stream:
        words = ElementTree.parse(stream).getroot()
    reference = {'um': [], 'uh': []}
    thirds = Counter()
    for word in words.iter('w'):
        if word.get('punc') == 'true' or not word.text:
            continue
        tokens = TOKEN.findall(word.text.lower().replace('’', "'"))
        if not tokens:
            continue
        start, end = (float(word.attrib[key]) for key in ('starttime', 'endtime'))
        if not 0 <= start <= end <= duration + .1:
            raise ValueError(f'{recording}: word timing outside recording: {start}, {end}')
        thirds[min(2, int(3 * (start + end) / (2 * duration)))] += len(tokens)
        filler = word.text.strip().lower()
        if filler in reference and start < end:
            reference[filler].append({'text': filler, 'start_s': start, 'end_s': end})
    reference['speaking_rate'] = round(60 * sum(thirds.values()) / duration, 1)
    reference['rate_changes'] = [round(180 * thirds[index] / duration, 1) for index in range(3)]
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('recording')
    parser.add_argument('duration', type=float)
    args = parser.parse_args()
    with ZipFile(args.archive) as archive:
        reference = word_references(archive, args.recording, args.duration)
    print(json.dumps(reference, indent=2))


if __name__ == '__main__':
    main()

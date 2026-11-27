"""Build independent filler, rate, and inter-segment pause references from AMI manual word timing."""

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


def segment_gap_references(archive, recording, duration):
    """Use gaps between manual speaker segments, excluding track edges."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('provide the complete recording duration in seconds')
    with archive.open(f'segments/{recording}.segments.xml') as stream:
        root = ElementTree.parse(stream).getroot()
    spans = sorted((float(node.attrib['transcriber_start']),
                    float(node.attrib['transcriber_end'])) for node in root.iter('segment'))
    gaps = []
    previous_end = None
    for start, end in spans:
        if not 0 <= start < end <= duration:
            raise ValueError(f'{recording}: segment timing outside recording: {start}, {end}')
        if previous_end is not None and start > previous_end:
            gaps.append({'start_s': previous_end, 'end_s': start})
        previous_end = end if previous_end is None else max(previous_end, end)
    if not spans:
        raise ValueError(f'{recording}: no manual speaker segments')
    return gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('recording')
    parser.add_argument('duration', type=float)
    args = parser.parse_args()
    with ZipFile(args.archive) as archive:
        reference = word_references(archive, args.recording, args.duration)
        reference['pauses'] = segment_gap_references(archive, args.recording, args.duration)
    print(json.dumps(reference, indent=2))


if __name__ == '__main__':
    main()

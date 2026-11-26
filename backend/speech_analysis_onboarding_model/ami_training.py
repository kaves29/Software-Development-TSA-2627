"""Export AMI train and development word spans for the continuous frame trainer."""

import argparse
import csv
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .ami_split import recording_splits

FIELDS = ('podcast_filename', 'clip_split_subset', 'episode_split_subset',
          'label_consolidated_vocab', 'event_start_inepisode', 'event_end_inepisode')


def word_rows(archive):
    splits = recording_splits(archive)
    for ami_split, trainer_split in (('training', 'train'), ('development', 'validation')):
        for row in splits[ami_split]:
            with archive.open(row['annotation']) as stream:
                words = ElementTree.parse(stream).getroot()
            for word in words.iter('w'):
                text = (word.text or '').strip().casefold()
                if not text or word.get('punc') == 'true':
                    continue
                start = word.get('starttime')
                end = word.get('endtime')
                if start is None or end is None or not 0 <= float(start) < float(end) < float('inf'):
                    continue
                yield (row['recording'], trainer_split, trainer_split,
                       text if text in {'um', 'uh'} else 'other', start, end)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with ZipFile(args.annotations) as archive, args.output.open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerows(word_rows(archive))


if __name__ == '__main__':
    main()

"""Score full-recording filler events against AMI word annotations."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .evaluate import recording_event_metrics


def filler_reference(archive, recording, duration):
    path = f'words/{recording}.words.xml'
    with archive.open(path) as stream:
        words = ElementTree.parse(stream).getroot()
    reference = []
    for word in words.iter('w'):
        label = (word.text or '').strip().lower()
        if label not in {'um', 'uh'} or word.get('punc') == 'true':
            continue
        start = float(word.attrib['starttime'])
        end = float(word.attrib['endtime'])
        if not 0 <= start < end <= duration:
            raise ValueError(f'{recording}: invalid filler timestamp {start}–{end}')
        reference.append({'text': label, 'start_s': start, 'end_s': end})
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('analyses', nargs='+', type=Path, metavar='MEETING.SPEAKER.json')
    args = parser.parse_args()
    rows = []
    seen = set()
    with ZipFile(args.annotations) as archive:
        for path in args.analyses:
            recording = path.stem
            if recording in seen:
                parser.error(f'duplicate speaker recording: {recording}')
            seen.add(recording)
            analysis = json.loads(path.read_text())
            duration = analysis['quality']['duration_s']
            rows.append({
                'duration_s': duration,
                'reference': filler_reference(archive, recording, duration),
                'predicted': analysis['features']['fillers']['value'],
            })
    print(json.dumps(recording_event_metrics(rows), indent=2))


if __name__ == '__main__':
    main()

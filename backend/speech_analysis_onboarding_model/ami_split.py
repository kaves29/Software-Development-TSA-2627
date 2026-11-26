"""Build a speaker-disjoint recording manifest from AMI split metadata."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


def recording_splits(archive):
    names = set(archive.namelist())
    with archive.open('corpusResources/meetings.xml') as stream:
        metadata = ElementTree.parse(stream).getroot()
    splits = {'training': [], 'development': [], 'test': []}
    speaker_splits = {}
    meetings_seen = set()
    earlier_meetings = {'ES2008a', 'TS3005a'}
    earlier_speakers = set()
    for meeting in metadata.iter('meeting'):
        visibility = meeting.get('visibility')
        split = 'test' if visibility == 'unseen' else meeting.get('seen_type')
        meeting_id = meeting.attrib['observation']
        if meeting_id in earlier_meetings:
            earlier_speakers.update(speaker.attrib['global_name'] for speaker in meeting.findall('speaker'))
        if split not in splits:
            continue
        if meeting_id in meetings_seen:
            raise ValueError(f'duplicate meeting: {meeting_id}')
        meetings_seen.add(meeting_id)
        slots = set()
        for speaker in meeting.findall('speaker'):
            global_id = speaker.attrib['global_name']
            slot = speaker.attrib['nxt_agent']
            if not global_id or not slot or slot in slots:
                raise ValueError(f'invalid or duplicate speaker slot in {meeting_id}')
            slots.add(slot)
            if speaker_splits.setdefault(global_id, split) != split:
                raise ValueError(f'speaker {global_id} crosses AMI splits')
            recording = f'{meeting_id}.{slot}'
            annotation = f'words/{recording}.words.xml'
            if annotation in names:
                splits[split].append({
                    'recording': recording,
                    'speaker': global_id,
                    'headset_channel': int(speaker.attrib['channel']),
                    'annotation': annotation,
                })
    if any(row['recording'].split('.')[0] in earlier_meetings or row['speaker'] in earlier_speakers
           for row in splits['test']):
        raise ValueError('previously evaluated recordings or speakers entered the test split')
    return splits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    args = parser.parse_args()
    with ZipFile(args.annotations) as archive:
        print(json.dumps(recording_splits(archive), indent=2))


if __name__ == '__main__':
    main()

"""Read timed events from AMI's manual disfluency layer."""

import re
from xml.etree import ElementTree

NITE = '{http://nite.sourceforge.net/}'
IDS = re.compile(r'id\(([^()]+)\)')


def repetition_references(archive, recording, duration):
    return disfluency_references(archive, recording, duration, 'ami_dsfl_12', nested=True)


def explicit_revision_references(archive, recording, duration):
    """Read explicit editing terms, the narrow revision class detected by Speakly."""
    return disfluency_references(archive, recording, duration, 'ami_dsfl_4', nested=False)


def disfluency_references(archive, recording, duration, ontology_id, *, nested):
    path = f'disfluency/{recording}.disfluency.xml'
    if path not in archive.namelist():
        return None
    with archive.open(path) as stream:
        annotations = ElementTree.parse(stream)
    with archive.open(f'words/{recording}.words.xml') as stream:
        words = [node for node in ElementTree.parse(stream).getroot()
                 if NITE + 'id' in node.attrib]
    indices = {node.attrib[NITE + 'id']: index for index, node in enumerate(words)}
    spans = set()
    untimed = 0
    for annotation in annotations.iter('dsfl'):
        if not any(pointer.get('role') == 'dsfl-type'
                   and pointer.get('href', '').endswith(f'#id({ontology_id})')
                   for pointer in annotation.findall(NITE + 'pointer')):
            continue
        positions = []
        components = annotation.findall('dsfl') if nested else [annotation]
        for component in components:
            for child in component.findall(NITE + 'child'):
                ids = IDS.findall(child.attrib['href'])
                if not 1 <= len(ids) <= 2 or any(key not in indices for key in ids):
                    raise ValueError(f'{recording}: unresolved {ontology_id} word link')
                positions.extend(range(indices[ids[0]], indices[ids[-1]] + 1))
        selected = [words[index] for index in positions
                    if words[index].tag == 'w' and words[index].get('punc') != 'true']
        if not selected or any(not {'starttime', 'endtime'} <= node.attrib.keys()
                               for node in selected):
            untimed += 1
            continue
        start = min(float(node.attrib['starttime']) for node in selected)
        end = max(float(node.attrib['endtime']) for node in selected)
        if not 0 <= start < end <= duration:
            untimed += 1
            continue
        spans.add((start, end))
    return {'events': [{'start_s': a, 'end_s': b} for a, b in sorted(spans)],
            'excluded_without_valid_timing': untimed}

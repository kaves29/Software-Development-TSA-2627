from io import BytesIO
from zipfile import ZipFile

from speech_analysis.ami_disfluency import explicit_revision_references, repetition_references


def test_repetition_references_resolve_ranges_and_preserve_unlabeled_tracks():
    with ZipFile(BytesIO(), 'w') as archive:
        archive.writestr('words/M.A.words.xml', '''
            <nite:root xmlns:nite="http://nite.sourceforge.net/">
                <w nite:id="w1" starttime="1.0" endtime="1.1">I</w>
                <w nite:id="w2" starttime="1.1" endtime="1.2">can</w>
                <w nite:id="w3" starttime="1.4" endtime="1.5">I</w>
                <w nite:id="w4" starttime="1.5" endtime="1.7">can</w>
            </nite:root>''')
        archive.writestr('disfluency/M.A.disfluency.xml', '''
            <nite:root xmlns:nite="http://nite.sourceforge.net/">
                <dsfl>
                    <nite:pointer role="dsfl-type" href="dsfl-types.xml#id(ami_dsfl_12)"/>
                    <dsfl><nite:child href="M.A.words.xml#id(w1)..id(w2)"/></dsfl>
                    <dsfl><nite:child href="M.A.words.xml#id(w3)..id(w4)"/></dsfl>
                </dsfl>
                <dsfl>
                    <nite:pointer role="dsfl-type" href="dsfl-types.xml#id(ami_dsfl_4)"/>
                    <nite:child href="M.A.words.xml#id(w3)..id(w4)"/>
                </dsfl>
            </nite:root>''')
        assert repetition_references(archive, 'M.A', 2) == {
            'events': [{'start_s': 1.0, 'end_s': 1.7}],
            'excluded_without_valid_timing': 0,
        }
        assert repetition_references(archive, 'M.B', 2) is None
        assert explicit_revision_references(archive, 'M.A', 2) == {
            'events': [{'start_s': 1.4, 'end_s': 1.7}],
            'excluded_without_valid_timing': 0,
        }
        assert explicit_revision_references(archive, 'M.B', 2) is None

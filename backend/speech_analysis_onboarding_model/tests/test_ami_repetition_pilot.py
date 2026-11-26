import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from speech_analysis_onboarding_model.experiments.ami_repetition_pilot import (
    _word_ids,
    read_words,
    reference_repetitions,
)


class AmiRepetitionAnnotationsTest(unittest.TestCase):
    def test_nested_repetition_resolves_word_range(self):
        words = '''<root xmlns:nite="http://nite.sourceforge.net/">
        <w nite:id="x.words1" starttime="1.0" endtime="1.2">a</w>
        <w nite:id="x.words2" starttime="1.2" endtime="1.4">a</w>
        <w nite:id="x.words3" starttime="1.4" endtime="1.4" punc="true">.</w>
        </root>'''
        labels = '''<root xmlns:nite="http://nite.sourceforge.net/"><dsfl>
        <nite:pointer role="dsfl-type" href="dsfl-types.xml#id(ami_dsfl_12)"/>
        <dsfl><nite:child href="x.words.xml#id(x.words1)..id(x.words3)"/></dsfl>
        </dsfl></root>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('words/x.words.xml', words)
                archive.writestr('disfluency/x.disfluency.xml', labels)
            with ZipFile(path) as archive:
                parsed, by_id = read_words(archive, 'x')
                self.assertEqual(len(parsed), 2)
                self.assertEqual(reference_repetitions(archive, 'x', by_id),
                                 [{'start_s': 1.0, 'end_s': 1.4}])
        with self.assertRaises(ValueError):
            _word_ids('x#id(x.words3)..id(y.words4)')


if __name__ == '__main__':
    unittest.main()

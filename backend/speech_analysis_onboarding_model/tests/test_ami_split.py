import io
import unittest
from zipfile import ZipFile

from speech_analysis_onboarding_model.ami_split import recording_splits
from speech_analysis_onboarding_model.ami_training import word_rows


class AmiSplitTest(unittest.TestCase):
    def test_rejects_shared_speaker_even_without_word_annotation(self):
        metadata = """
        <root>
          <meeting observation="one" visibility="seen" seen_type="training">
            <speaker nxt_agent="A" channel="0" global_name="shared"/>
          </meeting>
          <meeting observation="two" visibility="unseen">
            <speaker nxt_agent="B" channel="1" global_name="shared"/>
          </meeting>
        </root>
        """
        with ZipFile(io.BytesIO(), 'w') as archive:
            archive.writestr('corpusResources/meetings.xml', metadata)
            archive.writestr('words/two.B.words.xml', '<root/>')
            with self.assertRaisesRegex(ValueError, 'crosses AMI splits'):
                recording_splits(archive)

    def test_training_export_does_not_open_test_labels(self):
        metadata = """
        <root>
          <meeting observation="one" visibility="seen" seen_type="training">
            <speaker nxt_agent="A" channel="0" global_name="train"/>
          </meeting>
          <meeting observation="two" visibility="unseen">
            <speaker nxt_agent="A" channel="0" global_name="test"/>
          </meeting>
        </root>
        """
        with ZipFile(io.BytesIO(), 'w') as archive:
            archive.writestr('corpusResources/meetings.xml', metadata)
            archive.writestr('words/one.A.words.xml', """
                <root><w starttime="1" endtime="1.3">Um</w>
                <w starttime="1.4" endtime="1.8">example</w></root>""")
            archive.writestr('words/two.A.words.xml', 'intentionally unreadable')
            self.assertEqual(list(word_rows(archive)), [
                ('one.A', 'train', 'train', 'um', '1', '1.3'),
                ('one.A', 'train', 'train', 'other', '1.4', '1.8'),
            ])

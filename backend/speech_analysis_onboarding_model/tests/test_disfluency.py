import unittest
import io
import tempfile
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import soundfile as sf

from speech_analysis_onboarding_model.disfluency import labeled_repairs, clip_labels, DisfluencyClips


class DisfluencyLabelsTest(unittest.TestCase):
    def test_distinguishes_repetition_from_repair(self):
        events = labeled_repairs('I [ I, + I ] think [ they th-, + their tax ] deal')
        self.assertEqual([x['type'] for x in events], ['repetition', 'repair'])
        self.assertEqual(events[1]['reparandum'], 'they th-')

    def test_ignores_empty_or_malformed_markup(self):
        self.assertEqual(labeled_repairs('unfinished [ words + and [ + ]'), [])

    def test_repeated_phrase_is_not_confused_with_repair(self):
        events = labeled_repairs('[ the people + the people ] spoke')
        self.assertEqual(events[0]['type'], 'repetition')

    def test_clip_can_have_both_labels(self):
        result = clip_labels('[ I + I ] think [ they + we ] should go')
        self.assertEqual(result, (1, 1))
        self.assertEqual(clip_labels('No bracketed annotations.'), (0, 0))

    def test_dataset_decodes_resamples_and_filters_long_clips(self):
        def audio(seconds):
            stream = io.BytesIO()
            sf.write(stream, np.zeros(int(22050 * seconds)), 22050, format='WAV')
            return stream.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.parquet'
            pq.write_table(pa.Table.from_pylist([
                {'audio': {'bytes': audio(1), 'path': None}, 'transcript_annotated': '[ I + I ]'},
                {'audio': {'bytes': audio(13), 'path': None}, 'transcript_annotated': '[ a + b ]'},
            ]), path)
            dataset = DisfluencyClips([path])
            self.assertEqual(len(dataset), 1)
            waveform, labels = dataset[0]
            self.assertEqual(len(waveform), 16000)
            self.assertEqual(labels.tolist(), [1, 0])

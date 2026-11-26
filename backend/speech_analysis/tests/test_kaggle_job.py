import json
import tempfile
import unittest
from pathlib import Path

from speech_analysis.kaggle_job import select_candidate, notebook


class ComparisonTest(unittest.TestCase):
    def test_notebook_contains_disfluency_training_code(self):
        with tempfile.TemporaryDirectory() as directory:
            notebook('example', Path(directory))
            contents = (Path(directory) / 'train.ipynb').read_text()
            self.assertIn('train_disfluency.py', contents)
            self.assertIn('evaluate_disfluency.py', contents)

    def test_selects_best_validation_score_and_prefers_frozen_on_tie(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, score in [('frozen', 0.7), ('partial', 0.8), ('wavlm', 0.6)]:
                path = root / name
                path.mkdir()
                (path / 'metrics.json').write_text(json.dumps({'best_validation_filler_f1': score}))
            self.assertEqual(select_candidate(root), 'partial')
            (root / 'partial' / 'metrics.json').write_text(json.dumps({'best_validation_filler_f1': 0.7}))
            self.assertEqual(select_candidate(root), 'frozen')
            (root / 'wavlm' / 'metrics.json').write_text(json.dumps({'best_validation_filler_f1': 0.9}))
            self.assertEqual(select_candidate(root), 'wavlm')

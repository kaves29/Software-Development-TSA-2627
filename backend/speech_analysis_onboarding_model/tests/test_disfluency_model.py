import unittest
import subprocess
import sys
from types import SimpleNamespace

import torch
from torch import nn

from speech_analysis_onboarding_model.disfluency_model import DisfluencyClassifier, annotation_scores, collate, predict_segments


class FrameEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(hidden_size=1)

    def forward(self, waveform, attention_mask=None):
        return SimpleNamespace(last_hidden_state=waveform.unsqueeze(-1))

    def _get_feat_extract_output_lengths(self, lengths):
        return lengths


class DisfluencyModelTest(unittest.TestCase):
    def test_padding_is_excluded_from_normalization_and_pooling(self):
        model = DisfluencyClassifier(FrameEncoder()).eval()
        one = model(torch.tensor([[1., 2., 4.]]), torch.tensor([3]))
        padded = model(torch.tensor([[1., 2., 4., 900., 500.]]), torch.tensor([3]))
        self.assertTrue(torch.allclose(one, padded, atol=1e-6))
        self.assertEqual(tuple(one.shape), (1, 2))

    def test_batch_padding_and_multilabel_scores(self):
        batch = [(torch.tensor([1., 2.]), torch.tensor([1., 0.])),
                 (torch.tensor([3.]), torch.tensor([1., 1.]))]
        waves, lengths, targets = collate(batch)
        self.assertEqual(lengths.tolist(), [2, 1])
        self.assertEqual(waves.tolist(), [[1., 2.], [3., 0.]])
        scores = annotation_scores(torch.tensor([[1., -1.], [-1., 1.]]), targets)
        self.assertAlmostEqual(scores['repetition']['recall'], 0.5)
        self.assertAlmostEqual(scores['repair']['precision'], 1.0)

    def test_training_cli_requires_distinct_train_and_validation_arguments(self):
        result = subprocess.run([sys.executable, '-m', 'speech_analysis_onboarding_model.train_disfluency', '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--train', result.stdout)
        self.assertIn('--validation', result.stdout)

    def test_recording_cli_exposes_research_checkpoint(self):
        result = subprocess.run([sys.executable, '-m', 'speech_analysis_onboarding_model', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--disfluency-head', result.stdout)

    def test_heldout_evaluation_cli(self):
        result = subprocess.run([sys.executable, '-m', 'speech_analysis_onboarding_model.evaluate_disfluency', '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--test', result.stdout)

    def test_segment_predictions_indicate_regions_not_event_timestamps(self):
        class Fixed(nn.Module):
            def forward(self, waveform, lengths):
                return torch.tensor([[2.0, -2.0]])
        waveform = torch.ones(16000 * 13)
        result = predict_segments(Fixed(), waveform)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['start_s'], 0)
        self.assertEqual(result[0]['end_s'], 12)
        self.assertEqual(set(result[0]['probabilities']), {'repetition', 'repair'})

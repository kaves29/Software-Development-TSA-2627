import unittest
import tempfile
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

from speech_analysis_onboarding_model.fillers import FillerClassifier, save_checkpoint, load_checkpoint, checkpoint_encoder


class DummyEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(hidden_size=2)
        self.encoder = SimpleNamespace(layers=nn.ModuleList([nn.Linear(2, 2), nn.Linear(2, 2)]))
        self.layers = self.encoder.layers

    def forward(self, waveform):
        x = torch.stack((waveform[:, :2], waveform[:, 2:4]), dim=1)
        for layer in self.layers:
            x = layer(x)
        return SimpleNamespace(last_hidden_state=x)


class FillerTrainingTest(unittest.TestCase):
    def test_partial_finetuning_only_unfreezes_last_layer_and_head(self):
        model = FillerClassifier(DummyEncoder(), unfreeze_last=1)
        self.assertFalse(model.encoder.layers[0].weight.requires_grad)
        self.assertTrue(model.encoder.layers[1].weight.requires_grad)
        model(torch.randn(3, 4)).sum().backward()
        self.assertIsNotNone(model.encoder.layers[1].weight.grad)
        self.assertIsNotNone(model.head.weight.grad)

    def test_default_keeps_encoder_frozen(self):
        model = FillerClassifier(DummyEncoder())
        self.assertFalse(any(p.requires_grad for p in model.encoder.parameters()))

    def test_checkpoint_preserves_finetuned_encoder_and_legacy_head(self):
        with tempfile.TemporaryDirectory() as directory:
            source = FillerClassifier(DummyEncoder(), unfreeze_last=1)
            path = Path(directory) / 'model.pt'
            save_checkpoint(source, path)
            target = FillerClassifier(DummyEncoder(), unfreeze_last=1)
            load_checkpoint(target, path)
            self.assertTrue(torch.equal(source.encoder.layers[1].weight, target.encoder.layers[1].weight))
            torch.save(source.head.state_dict(), path)
            load_checkpoint(target, path)
            self.assertTrue(torch.equal(source.head.weight, target.head.weight))
            self.assertEqual(checkpoint_encoder(path), 'wav2vec2')

    def test_checkpoint_records_encoder_family(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.pt'
            model = FillerClassifier(DummyEncoder(), encoder_name='wavlm')
            save_checkpoint(model, path)
            self.assertEqual(checkpoint_encoder(path), 'wavlm')
            with self.assertRaises(ValueError):
                load_checkpoint(FillerClassifier(DummyEncoder()), path)

    def test_training_cli_exposes_partial_finetuning(self):
        script = Path(__file__).resolve().parents[1] / 'train_fillers.py'
        result = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--unfreeze-last', result.stdout)
        self.assertIn('--validation-only', result.stdout)
        self.assertIn('--evaluate-checkpoint', result.stdout)
        self.assertIn('--encoder', result.stdout)

    def test_same_windows_can_be_scored_at_different_thresholds(self):
        from speech_analysis_onboarding_model.fillers import select_filler_events

        windows = [
            {'text': 'um', 'start_s': 0, 'end_s': 1, 'score': .7},
            {'text': 'um', 'start_s': .25, 'end_s': 1.25, 'score': .9},
            {'text': 'uh', 'start_s': 2, 'end_s': 3, 'score': .6},
        ]
        self.assertEqual([e['start_s'] for e in select_filler_events(windows, .5)], [.25, 2])
        self.assertEqual([e['start_s'] for e in select_filler_events(windows, .85)], [.25])

    def test_transcript_gaps_require_detected_speech_and_preserve_explicit_fillers(self):
        from speech_analysis_onboarding_model.fillers import transcript_filler_candidates

        self.assertEqual(transcript_filler_candidates(
            [('Hi', .1, .3), ('um,', .6, .8), ('there', 1.3, 1.5)],
            [(0, 1.7)], 2),
            [(.3, .6, None), (.6, .8, 'um'), (.8, 1.3, None), (1.5, 1.7, None)])

    def test_frame_decoder_localizes_and_drops_short_isolated_predictions(self):
        from speech_analysis_onboarding_model.filler_frames import decode_frames

        background = [1, 0, 0]
        filler = [.05, .9, .05]
        rows = [background] * 3 + [filler] * 6 + [background] + [filler]
        self.assertEqual(decode_frames(rows, .22), [
            {'text': 'um', 'start_s': .06, 'end_s': .18, 'score': .9}
        ])

    def test_hysteresis_bridges_a_short_gap_but_requires_a_confident_frame(self):
        from speech_analysis_onboarding_model.filler_frames import decode_hysteresis

        rows = [[.4, .6, 0], [.1, .9, 0], [.9, .1, 0], [.4, .6, 0],
                [1, 0, 0], [1, 0, 0], [.4, .6, 0], [.4, .6, 0]]
        self.assertEqual(decode_hysteresis(rows, .16, onset=.8, continuation=.5,
                                          min_frames=3, max_gap=1),
                         [{'text': 'um', 'start_s': 0., 'end_s': .08, 'score': .9}])

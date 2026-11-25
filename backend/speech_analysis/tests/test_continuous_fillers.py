import unittest

import torch

from speech_analysis.train_filler_frames import continuous_targets


class ContinuousTargetTests(unittest.TestCase):
    def test_unknown_and_conflicting_frames_are_masked(self):
        labels = continuous_targets([(0.02, 0.06, 0), (0.04, 0.08, 1)], 5)
        torch.testing.assert_close(labels, torch.tensor([-100, 0, -100, 1, -100]))

    def test_agreeing_annotations_keep_the_label(self):
        labels = continuous_targets([(0.0, 0.04, 2), (0.02, 0.06, 2)], 4)
        torch.testing.assert_close(labels, torch.tensor([2, 2, 2, -100]))

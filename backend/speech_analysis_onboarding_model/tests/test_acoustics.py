import unittest

import numpy as np

from speech_analysis_onboarding_model.acoustics import energy_variation


class AcousticsTest(unittest.TestCase):
    def test_relative_energy_is_invariant_to_microphone_gain(self):
        signal = np.concatenate([np.full(16000, 0.05), np.full(16000, 0.1)])
        first = energy_variation(signal, 16000, [(0, 2)])
        second = energy_variation(signal * 2, 16000, [(0, 2)])
        self.assertAlmostEqual(first, second, places=4)
        self.assertGreater(first, 5)

    def test_silence_has_no_energy_estimate(self):
        self.assertIsNone(energy_variation(np.zeros(16000), 16000, [(0, 1)]))

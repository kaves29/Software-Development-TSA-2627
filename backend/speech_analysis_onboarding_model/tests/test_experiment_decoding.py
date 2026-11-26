import unittest

import numpy as np
from speech_analysis_onboarding_model.filler_frames import (
    decode_frames,
    decode_hysteresis,
)


class IndependentScoreTests(unittest.TestCase):
    def test_independent_decoder_accepts_confidence_below_half(self):
        scores = np.array([0.3] * 10)
        frames = np.column_stack((1 - scores, scores, np.zeros_like(scores)))
        # Multiclass argmax is not a valid way to lower an independent sigmoid threshold.
        self.assertEqual(decode_frames(frames, 0.2, threshold=0.2, min_frames=5), [])
        events = decode_hysteresis(frames, 0.2, onset=0.2, continuation=0.2, min_frames=5, max_gap=0)
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['start_s'], events[0]['end_s']), (0.0, 0.2))
        self.assertEqual(decode_hysteresis(frames, 0.2, onset=0.4, continuation=0.4, min_frames=5, max_gap=0), [])


if __name__ == '__main__':
    unittest.main()

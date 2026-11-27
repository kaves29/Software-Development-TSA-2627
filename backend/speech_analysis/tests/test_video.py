import unittest
from types import SimpleNamespace

from speech_analysis.video import observations, pose_fingertip_near_face


class VideoEvidenceTest(unittest.TestCase):
    def test_no_pose_abstains(self):
        self.assertTrue(all(row['value'] is None for row in observations([None] * 10).values()))

    def test_translation_and_hidden_wrists_are_distinct(self):
        frames = []
        for index in range(8):
            offset = index * .02
            pose = [SimpleNamespace(x=.5 + offset, y=.4, visibility=1, presence=1)
                    for _ in range(33)]
            pose[11].x -= .1
            pose[12].x += .1
            pose[15].visibility = 0
            frames.append(pose)
        evidence = observations(frames)
        self.assertAlmostEqual(evidence['torso_sway']['value'], .1)
        self.assertEqual(evidence['vertical_motion']['value'], 0)
        self.assertIsNone(evidence['left_hand_motion']['value'])
        self.assertEqual(evidence['right_hand_motion']['value'], 0)

    def test_proximity_requires_sustained_tracking_and_breaks_on_missing_frame(self):
        from speech_analysis.video import proximity_intervals

        states = [True, True, True, None, True, True, False, True, True, True]
        self.assertEqual(proximity_intervals([
            {'time_s': index / 5, 'fingertip_near_face': state}
            for index, state in enumerate(states)
        ]), [{'start_s': 0.0, 'end_s': 0.6}, {'start_s': 1.4, 'end_s': 2.0}])

    def test_background_shift_tracks_known_translation(self):
        import numpy as np
        from speech_analysis.video import background_shift

        rng = np.random.default_rng(24)
        frame = rng.integers(0, 256, (192, 192), dtype=np.uint8)
        pose = [SimpleNamespace(x=.5, y=.5, visibility=1, presence=1)]
        self.assertAlmostEqual(background_shift(frame, np.roll(frame, 5, axis=1), pose), 5, delta=.25)
        self.assertIsNone(background_shift(np.zeros_like(frame), np.zeros_like(frame), pose))


    def test_background_shift_tracks_rotation_and_zoom(self):
        import cv2
        import numpy as np
        from speech_analysis.video import background_shift

        rng = np.random.default_rng(24)
        frame = rng.integers(0, 256, (192, 192), dtype=np.uint8)
        pose = [SimpleNamespace(x=.5, y=.5, visibility=1, presence=1)]
        for angle, scale in ((4, 1), (0, 1.08)):
            with self.subTest(angle=angle, scale=scale):
                transform = cv2.getRotationMatrix2D((96, 96), angle, scale)
                moved = cv2.warpAffine(frame, transform, (192, 192))
                self.assertGreater(background_shift(frame, moved, pose), 3)


class ProximityReturnTests(unittest.TestCase):
    def test_missing_landmarks_do_not_count_as_a_return(self):
        from speech_analysis.video import observed_proximity_returns, proximity_intervals

        for separation, expected in (([None] * 3, 0), ([False, None, False], 0), ([False] * 3, 1)):
            with self.subTest(separation=separation):
                states = [True] * 3 + separation + [True] * 3
                frames = [{'time_s': i / 5, 'fingertip_near_face': state}
                          for i, state in enumerate(states)]
                self.assertEqual(observed_proximity_returns(frames, proximity_intervals(frames)), expected)


def test_absolute_face_yaw_extracts_rotation_without_scale_dependence():
    import numpy as np
    from speech_analysis.video import absolute_face_yaw

    angle = np.deg2rad(-35)
    transform = np.eye(4)
    transform[:3, 2] = 2 * np.array([np.sin(angle), 0, np.cos(angle)])
    np.testing.assert_allclose(absolute_face_yaw(transform), 35)
    transform[:3, 2] = 0
    assert absolute_face_yaw(transform) is None


def test_pose_proximity_distinguishes_visible_hands_from_missing_evidence():
    pose = [SimpleNamespace(x=.5, y=.5, visibility=0., presence=0.) for _ in range(33)]
    for index, x in ((0, .5), (11, .4), (12, .6)):
        pose[index] = SimpleNamespace(x=x, y=.5, visibility=1., presence=1.)
    assert pose_fingertip_near_face(pose) is None
    pose[19] = SimpleNamespace(x=.55, y=.5, visibility=.5, presence=.5)
    assert pose_fingertip_near_face(pose) is True
    pose[19].y = .7
    assert pose_fingertip_near_face(pose) is False

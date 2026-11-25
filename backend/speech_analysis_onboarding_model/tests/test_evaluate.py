import unittest

from speech_analysis_onboarding_model.evaluate import event_scores


class EventScoresTest(unittest.TestCase):
    def test_reference_cannot_be_reused_and_label_must_match(self):
        reference = [{'text': 'um', 'start_s': 1, 'end_s': 1.4}]
        predictions = [
            {'text': 'uh', 'start_s': 1, 'end_s': 1.4},
            {'text': 'um', 'start_s': 1.1, 'end_s': 1.5},
            {'text': 'um', 'start_s': 1.2, 'end_s': 1.6},
        ]
        scores = event_scores(predictions, reference, 0.25)
        self.assertEqual(scores['matches'], 1)
        self.assertAlmostEqual(scores['precision'], 1 / 3)
        self.assertAlmostEqual(scores['mean_boundary_error_s'], 0.1)

    def test_event_matching_can_reassign_a_prediction(self):
        references = [
            {'start_s': 1.0, 'end_s': 1.5},
            {'start_s': 1.3, 'end_s': 1.3},
        ]
        predictions = [
            {'start_s': 1.1, 'end_s': 1.4},
            {'start_s': 1.2, 'end_s': 1.7},
        ]
        self.assertEqual(event_scores(predictions, references, .25)['matches'], 2)

    def test_unavailable_recording_counts_as_a_miss(self):
        from speech_analysis_onboarding_model.evaluate import recording_event_metrics

        event = {'start_s': 1, 'end_s': 2}
        result = recording_event_metrics([
            {'duration_s': 10, 'predicted': [event], 'reference': [event]},
            {'duration_s': 10, 'predicted': None, 'reference': [event]},
        ])
        self.assertEqual(result['coverage'], .5)
        self.assertEqual(result['recall'], .5)
        self.assertAlmostEqual(result['f1'], 2 / 3)

    def test_full_recording_metrics_count_false_alarms_in_empty_reference(self):
        from speech_analysis_onboarding_model.evaluate import recording_event_metrics

        event = {'text': 'um', 'start_s': 5, 'end_s': 5.2}
        result = recording_event_metrics([
            {'duration_s': 30, 'predicted': [event], 'reference': [event]},
            {'duration_s': 30, 'predicted': [event], 'reference': []},
        ])
        self.assertEqual(result['false_alarms_per_minute'], 1)
        self.assertEqual(result['precision'], .5)
        self.assertAlmostEqual(result['f1'], 2 / 3)

    def test_video_interval_scoring_distinguishes_zero_events_from_missing_tracking(self):
        from speech_analysis_onboarding_model.evaluate import score

        event = {'start_s': 1, 'end_s': 1.6}
        reference = {'hand_near_face': [event]}
        for intervals, expected in (([event], 1), ([], 0)):
            features = {'hand_near_face': {'intervals': intervals}}
            self.assertEqual(score(features, reference)['hand_near_face']['f1'], expected)
        self.assertEqual(score({}, reference)['hand_near_face'],
                         {'status': 'insufficient_evidence'})

    def test_repeat_count_scores_zero_and_abstention_separately(self):
        from speech_analysis_onboarding_model.evaluate import score

        reference = {'hand_near_face_returns': 2}
        scored = score({'hand_near_face': {'observed_returns': 0}}, reference)
        self.assertEqual(scored['hand_near_face_returns'],
                         {'observed': 0, 'reference': 2, 'absolute_error': 2, 'exact_match': False})
        self.assertEqual(score({}, reference)['hand_near_face_returns'],
                         {'status': 'insufficient_evidence'})
        with self.assertRaises(ValueError):
            score({}, {'hand_near_face_returns': -1})

import json
import unittest
from unittest.mock import patch

from speech_analysis_onboarding_model.onboarding import (
    analyze_input,
    analyze_onboarding,
)


class OnboardingHandoffTests(unittest.TestCase):
    def test_audio_only_returns_readable_events_without_transcript(self):
        def audio(path, targets, prompt):
            self.assertEqual((path, targets, prompt), ('speech.wav', ['class'], 'My question'))
            return {'quality': {'duration_s': 20}, 'features': {
                'speaking_rate': {'status': 'estimated', 'value': 120},
                'fillers': {'status': 'experimental', 'value': [
                    {'text': 'um', 'start_s': 1.0, 'end_s': 1.2}]},
                'repetitions': {'status': 'experimental', 'value': [
                    {'text': 'private transcript', 'start_s': 2.0, 'end_s': 2.5}]},
            }}

        result = analyze_input('speech.wav', question='My question', targets=['class'], analyzer=audio)
        self.assertEqual(result['question'], 'My question')
        self.assertEqual(result['observations']['speaking_rate']['value'], 120)
        self.assertEqual(result['observations']['fillers']['value']['events'][0]['kind'], 'um')
        self.assertEqual(result['observations']['repetitions']['value']['count'], 1)
        self.assertIn('speaking rate: 120 words per minute', result['summary'])
        self.assertNotIn('private transcript', json.dumps(result))
        self.assertNotIn('speech.wav', json.dumps(result))
        self.assertNotIn('head_motion', result['observations'])

    def test_separate_video_file_and_missing_tracking_are_preserved(self):
        def audio(path, targets, prompt):
            return {'quality': {'duration_s': 15}, 'features': {'pauses': {'status': 'estimated', 'value': []}}}

        def video(path):
            self.assertEqual(path, 'camera.mp4')
            return {'quality': {'frames': 75}, 'features': {
                'head_motion': {'status': 'experimental', 'value': 0.2},
                'hand_near_face': {'status': 'insufficient_evidence', 'value': None}}}

        result = analyze_input('microphone.wav', video_path='camera.mp4', analyzer=audio, video_analyzer=video)
        self.assertEqual(result['observations']['head_motion']['modality'], 'video')
        self.assertEqual(result['observations']['head_motion']['value'], 0.2)
        self.assertIsNone(result['observations']['hand_near_face']['value'])
        self.assertEqual(result['quality']['video']['frames'], 75)
        json.dumps(result, allow_nan=False)

    def test_repeat_counts_are_preserved_when_tracking_is_available(self):
        def audio(path, targets, prompt):
            return {'quality': {}, 'features': {'pauses': {'status': 'estimated', 'value': []}}}

        def video(path):
            return {'quality': {}, 'features': {'hand_near_face': {
                'status': 'experimental', 'value': .2, 'observed_returns': 2}}}

        result = analyze_input('audio.wav', video_path='video.mp4', analyzer=audio, video_analyzer=video)
        self.assertEqual(result['observations']['hand_near_face']['observed_returns'], 2)
        self.assertIn('2 observed returns', result['summary'])
        self.assertEqual(result['analysis_status'], 'observations_available')

    def test_video_failure_and_audio_failure_do_not_become_predictions(self):
        def fail(*args):
            raise ValueError('private path')

        result = analyze_input('audio.wav', video_path='camera.mp4', analyzer=fail, video_analyzer=fail)
        self.assertIsNone(result['observations']['speaking_rate']['value'])
        self.assertIsNone(result['observations']['head_motion']['value'])
        self.assertNotIn('private path', json.dumps(result))
        self.assertEqual(result['quality']['video']['error'], 'ValueError')
        self.assertEqual(result['analysis_status'], 'unavailable')

    def test_failed_video_leaves_audio_result_and_marks_partial(self):
        def audio(*args):
            return {'quality': {}, 'features': {'pauses': {'status': 'estimated', 'value': []}}}

        def video(*args):
            raise ValueError('private error')

        result = analyze_input('audio.wav', video_path='video.mp4', analyzer=audio, video_analyzer=video)
        self.assertEqual(result['analysis_status'], 'partial')
        self.assertEqual(result['observations']['pauses']['value']['count'], 0)
        self.assertIsNone(result['observations']['head_motion']['value'])
        self.assertNotIn('private error', json.dumps(result))

    def test_default_pipeline_disables_openai_and_requires_pose_for_video(self):
        with self.assertRaises(ValueError):
            analyze_onboarding('audio.wav', video_path='camera.mp4')
        with patch('speech_analysis_onboarding_model.__main__.analyze_recording') as analyze:
            analyze.return_value = {'quality': {}, 'features': {'speaking_rate': {'status': 'estimated', 'value': 100}}}
            result = analyze_onboarding('audio.wav', question='Question')
            self.assertEqual(result['observations']['speaking_rate']['value'], 100)
            self.assertFalse(analyze.call_args.kwargs['content_openai'])


if __name__ == '__main__':
    unittest.main()

import unittest

from speech_analysis.handoff import roadmap_evidence


class HandoffTest(unittest.TestCase):
    def test_preserves_goals_and_disagreement_without_raw_text(self):
        profile = {'goal': 'class presentations', 'challenges': ['pace'],
                   'name': 'Private Name', 'age': 16, 'transcript': 'Private transcript'}
        session = {'observations': {'speaking_rate': {'coverage': 'multiple_samples', 'samples': [
            {'sample_id': 'a', 'status': 'estimated', 'value': 100},
            {'sample_id': 'b', 'status': 'estimated', 'value': 200},
        ]}, 'main_point': {'coverage': 'single_sample', 'samples': [
            {'sample_id': 'a', 'status': 'experimental', 'value': True, 'evidence': 'Private transcript'},
            {'sample_id': 'b', 'status': 'unavailable', 'value': None},
        ]}}}
        result = roadmap_evidence(profile, session)
        self.assertEqual(result['profile']['goal'], 'class presentations')
        self.assertEqual([x['value'] for x in result['audio_evidence']['speaking_rate']['samples']], [100, 200])
        self.assertNotIn('Private Name', str(result))
        self.assertNotIn('Private transcript', str(result))
        self.assertNotIn('age', result['profile'])
        self.assertEqual(result['audio_evidence']['main_point']['samples'][1]['status'], 'unavailable')

    def test_missing_evidence_does_not_become_a_negative_observation(self):
        result = roadmap_evidence({'goal': 'speaking'}, {'observations': {'fillers': {
            'coverage': 'insufficient_evidence', 'samples': [
                {'sample_id': 'a', 'status': 'unavailable', 'value': None},
                {'sample_id': 'b', 'status': 'unavailable', 'value': None},
            ]}}})
        self.assertIsNone(result['audio_evidence']['fillers']['samples'][0]['value'])

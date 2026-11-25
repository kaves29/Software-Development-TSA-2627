import unittest

from speech_analysis_onboarding_model.analysis import analyze_features


class AnalysisTest(unittest.TestCase):
    def test_timestamps_disfluencies_and_structure(self):
        words = [(word, i * 0.5, i * 0.5 + 0.4) for i, word in enumerate(
            'Um I I left I mean my point is clear for example cats'.split()
        )]
        result = analyze_features(8, [(0, 2), (3, 7)], words, ['cats', 'dogs'])
        self.assertEqual(len(result), 10)
        self.assertEqual(result['speaking_rate']['value'], 97.5)
        self.assertEqual(result['pauses']['value'], [{'start_s': 2, 'end_s': 3, 'duration_s': 1}])
        self.assertEqual(len(result['fillers']['value']), 1)
        self.assertEqual(len(result['repetitions']['value']), 1)
        self.assertEqual(len(result['revisions']['value']), 1)
        self.assertEqual(result['prompt_coverage']['value']['missing'], ['dogs'])
        self.assertEqual(result['organization']['status'], 'experimental')

    def test_empty_recording_has_no_invented_measurements(self):
        result = analyze_features(8, [], [], [])
        self.assertEqual(len(result), 10)
        self.assertTrue(all(item['value'] is None for item in result.values()))

    def test_failed_transcription_preserves_audio_observations(self):
        result = analyze_features(8, [(0, 2), (3, 7)], None, [], pitch_span=4.5)
        self.assertEqual(result['speaking_rate']['status'], 'unavailable')
        self.assertEqual(result['pitch_variation']['value'], 4.5)
        self.assertEqual(len(result['pauses']['value']), 1)

    def test_relative_energy_is_preserved_as_experimental_measurement(self):
        result = analyze_features(8, [(0, 6)], [], [], energy_span=5.7)
        self.assertEqual(result['energy_variation']['value'], 5.7)
        self.assertEqual(result['energy_variation']['status'], 'experimental')

    def test_multiword_repetitions_are_reported_once(self):
        words = [(word, i * 0.5, i * 0.5 + 0.4) for i, word in enumerate(
            'I think I think it works'.split()
        )]
        result = analyze_features(4, [(0, 4)], words, [])
        self.assertEqual(len(result['repetitions']['value']), 1)
        self.assertEqual(result['repetitions']['value'][0]['text'], 'i think i think')

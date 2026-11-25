import unittest
import tempfile
import json
import subprocess
import sys
from pathlib import Path

from speech_analysis_onboarding_model.session import combine_results
from speech_analysis_onboarding_model.session import analyze_session
from speech_analysis_onboarding_model.session import load_manifest


class SessionTest(unittest.TestCase):
    def test_preserves_sample_values_and_missing_evidence(self):
        samples = [
            {'id': 'one', 'result': {'quality': {}, 'features': {
                'pauses': {'status': 'estimated', 'value': [1]}}}},
            {'id': 'two', 'result': {'quality': {}, 'features': {
                'pauses': {'status': 'unavailable', 'value': None}}}},
        ]
        result = combine_results(samples)
        self.assertEqual(result['observations']['pauses']['coverage'], 'single_sample')
        self.assertEqual(result['observations']['pauses']['samples'][0]['value'], [1])
        self.assertEqual(result['observations']['pauses']['samples'][1]['status'], 'unavailable')

    def test_combined_report_omits_overlapping_legacy_text_heuristics(self):
        features = {'organization': {'status': 'experimental', 'value': {'point_marker': True}},
                    'prompt_coverage': {'status': 'experimental', 'value': {'matched': ['topic']}},
                    'main_point': {'status': 'experimental', 'value': True}}
        result = combine_results([{'id': 'a', 'result': {'features': features}},
                                  {'id': 'b', 'result': {'features': features}}])
        self.assertNotIn('organization', result['observations'])
        self.assertNotIn('prompt_coverage', result['observations'])
        self.assertIn('main_point', result['observations'])

    def test_requires_distinct_two_or_three_samples(self):
        with self.assertRaises(ValueError):
            combine_results([{'id': 'one', 'result': {}}])
        with self.assertRaises(ValueError):
            combine_results([{'id': 'one', 'result': {}}, {'id': 'one', 'result': {}}])

    def test_each_recording_is_analyzed_with_its_own_targets(self):
        def analyze(path, targets, prompt):
            return {'quality': {}, 'features': {'main_point': {
                'status': 'experimental', 'value': {'path': path, 'targets': targets, 'prompt': prompt}}}}
        result = analyze_session([
            {'id': 'one', 'path': 'a.wav', 'targets': ['school'], 'prompt': 'Explain'},
            {'id': 'two', 'path': 'b.wav', 'targets': ['work']},
        ], analyze)
        rows = result['observations']['main_point']['samples']
        self.assertEqual(rows[0]['value']['targets'], ['school'])
        self.assertEqual(rows[1]['value']['path'], 'b.wav')
        self.assertEqual(rows[0]['value']['prompt'], 'Explain')

    def test_failed_recording_does_not_discard_other_sample(self):
        def analyze(path, targets, prompt):
            if path == 'bad.wav':
                raise ValueError('private path or data should not be exposed')
            return {'quality': {}, 'features': {'pauses': {'status': 'estimated', 'value': []}}}
        result = analyze_session([
            {'id': 'one', 'path': 'bad.wav'}, {'id': 'two', 'path': 'good.wav'},
        ], analyze)
        self.assertEqual(result['observations']['pauses']['coverage'], 'single_sample')
        self.assertEqual(result['samples'][0]['quality']['errors'], ['recording: ValueError'])

    def test_manifest_resolves_paths_and_validates_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps({'recordings': [
                {'id': 'one', 'path': 'a.wav', 'targets': ['idea'], 'prompt': 'Explain an idea'},
                {'id': 'two', 'path': 'b.wav'},
            ]}))
            records = load_manifest(path)
            self.assertEqual(records[0]['path'], str(Path(directory) / 'a.wav'))
            self.assertEqual(records[1]['targets'], [])
            self.assertEqual(records[0]['prompt'], 'Explain an idea')
            path.write_text(json.dumps({'recordings': [
                {'id': 'one', 'path': 'a.wav', 'targets': 'idea'},
                {'id': 'two', 'path': 'b.wav'},
            ]}))
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_session_cli_reports_invalid_manifest_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{}')
            result = subprocess.run([sys.executable, '-m', 'speech_analysis_onboarding_model.session', str(path)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('manifest', result.stderr.lower())
            self.assertNotIn('Traceback', result.stderr)

    def test_total_failure_preserves_expected_fields(self):
        def fail(*args):
            raise ValueError('invalid recording')

        result = analyze_session([
            {'id': 'one', 'path': 'bad.mp4', 'video': True},
            {'id': 'two', 'path': 'bad.wav'},
        ], fail, fail)
        self.assertEqual(len(result['observations']), 30)
        self.assertTrue(all(row['coverage'] == 'insufficient_evidence'
                            for row in result['observations'].values()))


class ProximitySessionTests(unittest.TestCase):
    def test_only_detailed_video_contributes_to_proximity_returns(self):
        from speech_analysis_onboarding_model.session import combine_results

        features = [
            {'hand_near_face': {'status': 'experimental', 'value': .3, 'observed_returns': 1}},
            {'hand_near_face': {'status': 'experimental', 'value': .2}},
            {},
        ]
        report = combine_results([{'id': str(i), 'result': {'features': row}}
                                  for i, row in enumerate(features)])
        self.assertEqual(report['observations']['hand_near_face']['proximity_returns'],
                         {'tracked_sample_ids': ['0'], 'sample_ids_with_returns': ['0']})

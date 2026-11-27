import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from speech_analysis.roadmap import create_app


class RoadmapTest(unittest.TestCase):
    def request(self, goal='Class presentation', samples=2):
        return {'confirmed': True, 'goal': goal, 'profile': {'name': 'Private'},
                'samples': [{'id': str(i), 'result': {'features': {
                    'speaking_rate': {'status': 'estimated', 'value': 120 + i},
                    'main_point': {'status': 'experimental', 'value': False},
                }}} for i in range(samples)]}

    def test_confirmed_profiles_and_recordings_reach_provider(self):
        def provider(payload):
            self.assertNotIn('main_point', payload['observations'])
            self.assertNotIn('name', payload['profile'])
            goal = payload['profile']['goal']
            return {'weeks': [{'theme': goal, 'outcome': 'Practice', 'rationale': 'Goal'}] * 10,
                    'current_week': [{'catalog_id': 'outline', 'instructions': goal}] * 7}

        client = TestClient(create_app(provider))
        for count, goal in [(2, 'Present a project'), (3, 'Practice interviews')]:
            response = client.post('/api/roadmap/generate', json=self.request(goal, count))
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['weeks'][0]['theme'], goal)
            self.assertEqual(len(data['recording_quality']), count)
            self.assertEqual(sum(day['duration_minutes'] for day in data['current_week']), 70)

    def test_mock_requires_no_secret_and_invalid_provider_is_rejected(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            response = TestClient(create_app()).post('/api/roadmap/generate', json=self.request())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['generation_mode'], 'mock')
        self.assertEqual(TestClient(create_app(lambda _: {})).post(
            '/api/roadmap/generate', json=self.request()).status_code, 502)

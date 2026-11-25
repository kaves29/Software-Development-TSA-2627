import unittest
import json
from unittest.mock import patch

from speech_analysis.content import parse_content_result, analyze_content, content_from_words, openai_provider


class ContentTest(unittest.TestCase):
    def test_result_requires_exact_supporting_quote(self):
        transcript = 'My point is practice helps. For example I speak every day.'
        response = {
            'main_point': {'present': True, 'quote': 'My point is practice helps.'},
            'supporting_detail': {'present': True, 'quote': 'invented words'},
            'transitions': {'present': False, 'quote': ''},
            'closing': {'present': None, 'quote': ''},
            'prompt_relevance': {'present': True, 'quote': 'I speak every day.'},
        }
        result = parse_content_result(response, transcript, prompt='How do you practice?')
        self.assertEqual(result['main_point']['status'], 'experimental')
        self.assertEqual(result['supporting_detail']['status'], 'insufficient_evidence')
        self.assertEqual(result['closing']['status'], 'insufficient_evidence')
        self.assertEqual(result['transitions']['value'], False)

    def test_absent_prompt_does_not_claim_relevance(self):
        response = {'prompt_relevance': {'present': True, 'quote': 'Hello world'}}
        result = parse_content_result(response, 'Hello world', prompt='')
        self.assertEqual(result['prompt_relevance']['status'], 'insufficient_evidence')

    def test_prompt_completion_requires_prompt_context(self):
        response = {'prompt_completion': {'present': True, 'quote': 'Hello world'}}
        result = parse_content_result(response, 'Hello world', prompt='')
        self.assertEqual(result['prompt_completion']['status'], 'insufficient_evidence')

    def test_missing_key_returns_unavailable_without_calling_provider(self):
        def provider(*args):
            raise AssertionError('provider must not be called')
        result = analyze_content('Hello world', 'Say hello', '', provider=provider)
        self.assertTrue(all(x['status'] == 'unavailable' for x in result.values()))

    def test_provider_failure_returns_safe_unavailable_results(self):
        def provider(*args):
            raise RuntimeError('secret information')
        result = analyze_content('Hello world', 'Say hello', 'key', provider=provider)
        self.assertTrue(all(x['status'] == 'unavailable' for x in result.values()))
        self.assertNotIn('secret', str(result))

    def test_content_from_words_uses_transcript_without_returning_it(self):
        def provider(transcript, prompt, key, model):
            self.assertEqual(transcript, 'A clear point')
            return {'main_point': {'present': True, 'quote': 'clear point'}}
        result = content_from_words([('A', 0, 1), ('clear', 1, 2), ('point', 2, 3)],
                                    'Prompt', 'key', provider=provider)
        self.assertEqual(result['main_point']['evidence'], 'clear point')
        self.assertNotIn('transcript', result)

    def test_openai_request_is_structured_and_requests_no_storage(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return json.dumps({'output': [{'content': [{'type': 'output_text',
                    'text': json.dumps({'main_point': {'present': True, 'quote': 'hello'}})}]}]}).encode()
        with patch('speech_analysis.content.urllib.request.urlopen', return_value=Response()) as call:
            answer = openai_provider('hello', 'greet', 'sample-secret', 'gpt-4o-mini')
        request = call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload['store'])
        self.assertEqual(payload['text']['format']['type'], 'json_schema')
        self.assertNotIn('sample-secret', request.data.decode())
        self.assertEqual(answer['main_point']['quote'], 'hello')

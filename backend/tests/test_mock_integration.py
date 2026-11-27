"""Onboarding must work with mocks and never call OpenAI during development."""

from fastapi.testclient import TestClient

from backend.main import app


def answers():
    return {
        'question_version': '1', 'name': 'Private', 'age': 16, 'language': 'English',
        'motivation': ['Do better at school'], 'outcomes': ['Explain ideas clearly'],
        'challenges': ['I lose my train of thought'], 'situation': 'Giving a presentation',
        'priority': 'Explain ideas clearly',
    }


def test_mock_flow_never_calls_openai_even_with_configured_key(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('live provider used during mock flow')

    monkeypatch.setenv('OPENAI_API_KEY', 'not-a-real-key')
    monkeypatch.setattr('backend.onboarding.OpenAI', no_network)
    monkeypatch.setattr('backend.speech_analysis.roadmap.urlopen', no_network)
    monkeypatch.setattr('backend.recordings.analyze_media', lambda path, prompt, video: {
        'features': {
            'speaking_rate': {'status': 'estimated', 'value': 120},
            'left_hand_motion': {'status': 'experimental', 'value': .15 if video else None},
            'fillers': {'status': 'experimental', 'value': [{'text': 'uh', 'start_s': 1, 'end_s': 1.2}]},
        },
        'quality': {'duration_s': 20},
    })
    client = TestClient(app)
    followups = client.post('/v1/onboarding/follow-ups', json=answers())
    assert followups.status_code == 200
    assert len(followups.json()['questions']) == 2
    samples = []
    for video in ('false', 'true'):
        res = client.post('/v1/onboarding/recordings', files={'file': ('sample.wav', b'audio')},
                          data={'prompt': 'Explain a topic.', 'video': video})
        assert res.status_code == 200
        samples.append(res.json())
    res = client.post('/v1/onboarding/roadmap', json={
        'confirmed': True, 'goal': 'Explain ideas clearly', 'answers': answers(),
        'follow_up_answers': {'follow_up_1': 'During transitions'}, 'samples': samples,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body['weeks']) == 10 and len(body['current_week']) == 7
    assert all(item['duration_minutes'] == 10 for item in body['current_week'])
    assert 'Private' not in str(body['evidence'])
    assert body['evidence']['audio_evidence']['speaking_rate']['coverage'] == 'multiple_samples'
    assert body['evidence']['audio_evidence']['left_hand_motion']['coverage'] == 'single_sample'


def test_recording_adapter_passes_configured_filler_head(monkeypatch, tmp_path):
    from backend.recordings import analyze_media
    from backend.speech_analysis import __main__ as audio

    head = tmp_path / 'filler.pt'
    head.write_bytes(b'not a real checkpoint')
    monkeypatch.setenv('SPEAKLY_FILLER_HEAD', str(head))
    def fake_audio(path, targets, model, cache, filler_head=None, **kwargs):
        assert filler_head == str(head)
        assert kwargs.get('content_openai', False) is False
        return {'features': {}, 'quality': {}}
    monkeypatch.setattr(audio, 'analyze_recording', fake_audio)
    assert analyze_media(tmp_path / 'audio.wav', 'A prompt', False)['features'] == {}


def test_frame_filler_checkpoint_is_used_by_audio_analyzer(monkeypatch, tmp_path):
    import numpy as np
    import torch
    import whisper
    import librosa
    import silero_vad
    from types import SimpleNamespace
    from transformers import AutoModel
    from backend.speech_analysis import __main__ as audio, filler_frames

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = SimpleNamespace(layers=[])
            self.config = SimpleNamespace(hidden_size=8)

    head = tmp_path / 'frame.pt'
    torch.save({'kind': 'frame_filler', 'encoder_name': 'wavlm', 'window_samples': 64000,
                'head': torch.nn.Linear(8, 3).state_dict()}, head)
    monkeypatch.setattr(audio, 'decode_audio', lambda path: np.zeros(32000, dtype='float32'))
    monkeypatch.setattr(silero_vad, 'load_silero_vad', lambda: object())
    monkeypatch.setattr(silero_vad, 'get_speech_timestamps', lambda *a, **k: [{'start': 0, 'end': 32000}])
    monkeypatch.setattr(whisper, 'load_model', lambda *a, **k: SimpleNamespace(
        transcribe=lambda *a, **k: {'segments': [{'words': [{'word': 'hello', 'start': .2, 'end': .5}]}]}))
    monkeypatch.setattr(librosa, 'pyin', lambda *a, **k: (np.ones(20) * 100, np.ones(20, dtype=bool), None))
    monkeypatch.setattr(AutoModel, 'from_pretrained', lambda *a, **k: Encoder())
    monkeypatch.setattr(filler_frames, 'score_recording', lambda model, waveform, **kwargs: [[.01, .98, .01]] * 13)
    result = audio.analyze_recording('fixture.wav', [], 'tiny.en', None, str(head))
    assert result['quality']['errors'] == []
    assert result['features']['fillers']['value'][0]['text'] == 'um'
    assert 'frame' in result['features']['fillers']['method']
    fallback = audio.analyze_recording('fixture.wav', [], 'tiny.en', None)
    assert fallback['features']['fillers']['method'] == 'transcript heuristic'


def test_video_adapter_passes_configured_research_models(monkeypatch, tmp_path):
    from backend.recordings import analyze_media
    from backend.speech_analysis import __main__ as audio, video

    pose = tmp_path / 'pose.task'
    pose.touch()
    monkeypatch.setenv('SPEAKLY_POSE_MODEL', str(pose))
    monkeypatch.setenv('SPEAKLY_POSE_FINGERTIP_PROXIMITY', '1')
    monkeypatch.setattr(audio, 'analyze_recording', lambda *a, **kw: {'features': {}, 'quality': {}})
    def fake_video(path, model, **kwargs):
        assert model == pose
        assert kwargs['pose_fingertip_proximity'] is True
        return {'features': {'hand_near_face': {'status': 'experimental', 'value': .2}}, 'quality': {}}
    monkeypatch.setattr(video, 'analyze_video', fake_video)
    assert analyze_media(tmp_path / 'clip.mp4', 'A prompt', True)['features']['hand_near_face']['value'] == .2


def test_latest_main_recording_endpoint_remains_supported(monkeypatch):
    from pathlib import Path
    paths = []
    def fake(path, prompt, video):
        assert Path(path).read_bytes() == b'clip'
        paths.append(path)
        assert (prompt, video) == ('Explain your goal', True)
        return {'quality': {}, 'features': {'speaking_rate': {'status': 'estimated', 'value': 100}}}
    monkeypatch.setattr('backend.recordings.analyze_media', fake)
    client = TestClient(app)
    result = client.post('/v1/onboarding/recordings/analyze',
                         data={'sample_id': 'sample-1', 'prompt': 'Explain your goal', 'media_type': 'video'},
                         files={'recording': ('clip.mp4', b'clip', 'video/mp4')})
    assert result.status_code == 200
    assert result.json()['id'] == 'sample-1'
    assert not paths[0].exists()
    bad = client.post('/v1/onboarding/recordings/analyze',
                      data={'sample_id': ' ', 'prompt': ' ', 'media_type': 'other'},
                      files={'recording': ('clip.mp4', b'clip', 'video/mp4')})
    assert bad.status_code == 422


def test_mock_outputs_reflect_distinct_profiles_and_require_confirmed_profile(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'not-a-real-key')
    monkeypatch.setattr('backend.onboarding.OpenAI', lambda **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    client = TestClient(app)
    first = answers()
    second = {**answers(), 'outcomes': ['Speak at a comfortable pace'],
              'challenges': ['Rush or speak too slowly'], 'priority': 'Speak at a comfortable pace'}
    first_q = client.post('/v1/onboarding/follow-ups', json=first)
    second_q = client.post('/v1/onboarding/follow-ups', json=second)
    assert first_q.status_code == second_q.status_code == 200
    assert first_q.json()['questions'][0]['prompt'] != second_q.json()['questions'][0]['prompt']
    samples = [{'id': str(i), 'result': {'features': {}}} for i in range(2)]
    def make_request(profile, confirmed=True):
        return client.post('/v1/onboarding/roadmap', json={'confirmed': confirmed,
            'goal': profile['priority'], 'answers': profile, 'samples': samples})
    assert make_request(first, confirmed=False).status_code == 422
    first_map, second_map = make_request(first).json(), make_request(second).json()
    assert first_map['generation_mode'] == second_map['generation_mode'] == 'mock'
    assert first_map['current_week'][1]['catalog_id'] == 'outline'
    assert second_map['current_week'][1]['catalog_id'] == 'pace'


def test_mock_roadmap_rejects_duplicate_samples():
    client = TestClient(app)
    sample = {'id': 'same', 'result': {'features': {}}}
    response = client.post('/v1/onboarding/roadmap', json={'confirmed': True,
        'goal': 'Explain ideas clearly', 'answers': answers(), 'samples': [sample, sample]})
    assert response.status_code == 422


def test_future_roadmap_provider_request_is_wired_without_network(monkeypatch):
    import io
    import json
    from backend.speech_analysis import roadmap

    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    expected = {'weeks': [{'theme': 'Focus', 'outcome': 'Practice', 'rationale': 'Goal'}] * 10,
                'current_week': [{'catalog_id': 'pace', 'instructions': 'Practice.'}] * 7}
    def fake_urlopen(request, timeout):
        assert request.full_url == 'https://api.openai.com/v1/responses'
        body = json.loads(request.data)
        assert body['model'] == 'gpt-5.4-mini'
        assert body['store'] is False
        assert body['text']['format']['strict'] is True
        return io.BytesIO(json.dumps({'output': [{'content': [{'type': 'output_text',
                                 'text': json.dumps(expected)}]}]}).encode())
    monkeypatch.setattr(roadmap, 'urlopen', fake_urlopen)
    assert roadmap.openai_roadmap({'profile': {'goal': 'practice'}, 'observations': {}}, 'test-only') == expected


def test_three_sample_roadmap_preserves_missing_and_experimental_evidence(monkeypatch):
    from backend.speech_analysis import roadmap
    original = roadmap.mock_roadmap
    captured = {}
    def provider(payload):
        captured.update(payload)
        return original(payload)
    monkeypatch.setattr(roadmap, 'mock_roadmap', provider)
    samples = [
        {'id': 'a', 'result': {'features': {'speaking_rate': {'status': 'estimated', 'value': 110}}}},
        {'id': 'b', 'result': {'features': {'speaking_rate': {'status': 'unavailable', 'value': None},
                     'hand_near_face': {'status': 'experimental', 'value': .2}}}},
        {'id': 'c', 'result': {'features': {'speaking_rate': {'status': 'estimated', 'value': 140}}}},
    ]
    response = TestClient(app).post('/v1/onboarding/roadmap', json={
        'confirmed': True, 'goal': 'Explain ideas clearly', 'answers': answers(),
        'follow_up_answers': {'follow_up_1': 'Between ideas', 'follow_up_2': 'Within a month'},
        'samples': samples,
    })
    assert response.status_code == 200
    assert captured['profile']['follow_up_answers']['follow_up_1'] == 'Between ideas'
    assert 'name' not in captured['profile'] and 'age' not in captured['profile']
    assert captured['observations']['speaking_rate'] == [
        {'sample_index': 1, 'status': 'estimated', 'value': 110},
        {'sample_index': 3, 'status': 'estimated', 'value': 140},
    ]
    assert captured['observations']['hand_near_face'] == [
        {'sample_index': 2, 'status': 'experimental', 'value': .2}]
    evidence = response.json()['evidence']['audio_evidence']['speaking_rate']
    assert evidence['samples'][1]['status'] == 'unavailable'
    assert evidence['samples'][1]['value'] is None

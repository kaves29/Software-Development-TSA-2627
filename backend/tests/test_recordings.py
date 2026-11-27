from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_recording_handoff_and_cleanup(monkeypatch):
    captured = {}

    def analyze(path, prompt, video):
        captured["path"] = path
        assert path.read_bytes() == b"sample recording"
        assert prompt == "Tell us about a project."
        assert video is True
        return {"quality": {}, "features": {"speaking_rate": {"status": "estimated", "value": 120}}}

    monkeypatch.setattr("backend.recordings.analyze_sample", analyze)
    response = client.post(
        "/v1/onboarding/recordings/analyze",
        data={"sample_id": "sample-1", "prompt": "Tell us about a project.", "media_type": "video"},
        files={"recording": ("clip.webm", b"sample recording", "video/webm")},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "sample-1"
    assert response.json()["result"]["features"]["speaking_rate"]["value"] == 120
    assert not captured["path"].exists()


def test_rejects_empty_recording():
    response = client.post(
        "/v1/onboarding/recordings/analyze",
        data={"sample_id": "one", "prompt": "Say hello.", "media_type": "audio"},
        files={"recording": ("clip.webm", b"", "audio/webm")},
    )
    assert response.status_code == 422


def test_missing_model_returns_safe_error_and_cleans_up(monkeypatch):
    paths = []

    def fail(path, prompt, video):
        paths.append(path)
        raise RuntimeError("private path")

    monkeypatch.setattr("backend.recordings.analyze_sample", fail)
    response = client.post(
        "/v1/onboarding/recordings/analyze",
        data={"sample_id": "one", "prompt": "Say hello.", "media_type": "video"},
        files={"recording": ("clip.webm", b"clip", "video/webm")},
    )
    assert response.status_code == 503
    assert "private path" not in response.text
    assert not paths[0].exists()

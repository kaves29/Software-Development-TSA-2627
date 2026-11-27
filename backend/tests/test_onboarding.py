import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.onboarding import FollowUpResponse

client = TestClient(app)


@pytest.fixture
def answers():
    return {
        "question_version": "1", "name": "Sam", "age": 16, "language": "English",
        "motivation": ["Do better at school"], "outcomes": ["Explain ideas clearly"],
        "challenges": ["I lose my train of thought"], "situation": "Giving a presentation",
        "priority": "Explain ideas clearly",
    }


def test_followups_with_valid_answers(monkeypatch, answers):
    result = FollowUpResponse.model_validate({"questions": [
        {"id": "follow_up_1", "prompt": "When do you lose your place?",
         "options": ["At the start", "During transitions", "Other"]},
        {"id": "follow_up_2", "prompt": "What would you like to practice first?",
         "options": ["An opening", "A transition", "Other"]},
    ]})
    monkeypatch.setattr("backend.main.generate_followups", lambda value: result)
    response = client.post("/v1/onboarding/follow-ups", json=answers)
    assert response.status_code == 200
    assert response.json() == result.model_dump()


@pytest.mark.parametrize("field,value", [
    ("age", True), ("age", 0), ("motivation", ["Not an option"]),
    ("outcomes", ["Explain ideas clearly", "Explain ideas clearly"]),
    ("priority", "Not selected"), ("situation", "Other"),
    ("question_version", "2"),
])
def test_invalid_answers_rejected(monkeypatch, answers, field, value):
    answers[field] = value
    monkeypatch.setattr("backend.main.generate_followups", lambda value: pytest.fail("Provider called"))
    assert client.post("/v1/onboarding/follow-ups", json=answers).status_code == 422


def test_missing_key_is_safe(monkeypatch, answers):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/v1/onboarding/follow-ups", json=answers)
    assert response.status_code == 503
    assert response.json()["detail"] == "AI follow-ups are not configured."


def test_other_text_is_accepted(monkeypatch, answers):
    answers["situation"] = "Other"
    answers["other_details"] = {"situation": "A club meeting"}
    monkeypatch.setattr("backend.main.generate_followups", lambda value: (_ for _ in ()).throw(
        __import__("backend.onboarding", fromlist=["ProviderUnavailable"]).ProviderUnavailable("test")))
    assert client.post("/v1/onboarding/follow-ups", json=answers).status_code == 503


def test_provider_receives_no_name_or_age(monkeypatch, answers):
    import json
    from types import SimpleNamespace
    from backend.onboarding import InitialAnswers, generate_followups

    response = FollowUpResponse.model_validate({"questions": [
        {"id": "follow_up_1", "prompt": "When is it hardest?",
         "options": ["Beginning", "Middle", "Other"]},
        {"id": "follow_up_2", "prompt": "What should you practice?",
         "options": ["Openings", "Transitions", "Other"]},
    ]})

    class FakeCompletions:
        def parse(self, **kwargs):
            model_input = json.loads(kwargs["messages"][1]["content"])
            assert "name" not in model_input
            assert "age" not in model_input
            assert model_input["situation"] == "Giving a presentation"
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=response))])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("backend.onboarding.OpenAI", lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())))
    assert generate_followups(InitialAnswers.model_validate(answers)) == response


def test_invalid_model_output_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        FollowUpResponse.model_validate({"questions": [
            {"id": "follow_up_1", "prompt": "Question?", "options": ["A", "B"]},
            {"id": "follow_up_2", "prompt": "Question?", "options": ["A", "Other"]},
        ]})

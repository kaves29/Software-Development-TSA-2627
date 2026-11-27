from fastapi import FastAPI
from pydantic import BaseModel, Field


class Question(BaseModel):
    id: str
    prompt: str
    type: str
    required: bool = True
    options: list[str] = Field(default_factory=list)
    description: str | None = None


class QuestionSet(BaseModel):
    version: str
    questions: list[Question]


app = FastAPI(title="Speakly onboarding API", version="0.1.0")

QUESTIONS = QuestionSet(
    version="1",
    questions=[
        Question(id="age", prompt="How old are you?", type="number",
                 description="Enter your age in years, not your date of birth."),
        Question(id="language", prompt="Are you ready to practice in English?",
                 type="single_select", options=["Yes"]),
        Question(id="situations", prompt="Where would you like to practice speaking?",
                 type="multi_select", options=["Presentations", "Class participation",
                 "Interviews", "Conversations", "Explaining ideas", "Other"]),
        Question(id="goals", prompt="What would you like to achieve?",
                 type="multi_select", options=["Express ideas clearly", "Organize my thoughts",
                 "Engage listeners", "Feel more prepared", "Other"]),
        Question(id="challenges", prompt="What would you like to work on?",
                 type="multi_select", options=["Getting started", "Organizing ideas",
                 "Speaking clearly", "Voice projection", "Pacing and pauses",
                 "Engaging listeners", "Gestures and posture", "Everyday nerves", "Other"]),
        Question(id="commitment", prompt="Can you practice for ten minutes each day?",
                 type="single_select", options=["Yes", "I need flexibility"],
                 description="The prototype roadmap uses ten minutes each day."),
        Question(id="preferences", prompt="How do you prefer to practice?",
                 type="multi_select", options=["Guided steps", "Examples",
                 "Independent practice", "Reflection", "Other"]),
        Question(id="constraints", prompt="Is there anything else that would help shape your practice?",
                 type="text", required=False,
                 description="Please do not include medical or identifying information."),
    ],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/onboarding/questions", response_model=QuestionSet)
def onboarding_questions() -> QuestionSet:
    return QUESTIONS

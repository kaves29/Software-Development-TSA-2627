from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.onboarding import InitialAnswers, FollowUpResponse, ProviderUnavailable, ShortText, generate_followups
from backend.recordings import router as recordings_router
from backend.speech_analysis.roadmap import Onboarding, generate_roadmap


class Question(BaseModel):
    id: str
    prompt: str
    type: str
    required: bool = True
    options: list[str] = Field(default_factory=list)
    description: str | None = None
    max_selections: int | None = None


class QuestionSet(BaseModel):
    version: str
    questions: list[Question]


app = FastAPI(title="Speakly onboarding API", version="0.1.0")
app.include_router(recordings_router)

QUESTIONS = QuestionSet(
    version="1",
    questions=[
        Question(id="name", prompt="What is your name?", type="text"),
        Question(id="age", prompt="How old are you?", type="number",
                 description="Enter your age in years, not your date of birth."),
        Question(id="language", prompt="What is your preferred language?", type="text",
                 description="Practice is currently available in English only."),
        Question(id="motivation", prompt="Why do you want to improve your speaking?",
                 type="multi_select", max_selections=2,
                 options=["Do better at school", "Grow at work", "Prepare for a job or college",
                          "Feel more comfortable in everyday life", "Connect with people",
                          "Work toward a personal goal", "Other"]),
        Question(id="outcomes", prompt="What would you most like to be able to do?",
                 type="multi_select", max_selections=2,
                 options=["Explain ideas clearly", "Organize my thoughts", "Speak at a comfortable pace",
                          "Be heard clearly", "Keep people interested", "Respond without much preparation",
                          "Use body language effectively", "Other"]),
        Question(id="challenges", prompt="What usually gets in the way when you try to do that?",
                 type="multi_select", max_selections=2,
                 options=["I lose my train of thought", "Rush or speak too slowly", "Struggle to find words",
                          "Speak too quietly", "Feel nervous", "Have trouble holding attention",
                          "Feel unsure what to do with my body", "Other"]),
        Question(id="situation", prompt="Think of a recent time that happened. What were you doing?",
                 type="single_select", options=["Giving a presentation", "Answering a question",
                 "Talking one-on-one", "Speaking in a group", "Interviewing", "Other"]),
        Question(id="situation_details", prompt="What happened?", type="text", required=False,
                 description="Please do not include medical or identifying information."),
        Question(id="priority", prompt="Which one matters most to you right now?",
                 type="single_select", description="Choose from the outcomes and challenges you selected."),
    ],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/onboarding/questions", response_model=QuestionSet)
def onboarding_questions() -> QuestionSet:
    return QUESTIONS


@app.post("/v1/onboarding/follow-ups", response_model=FollowUpResponse)
def follow_up_questions(answers: InitialAnswers) -> FollowUpResponse:
    validate_answers(answers)
    try:
        return generate_followups(answers)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def validate_answers(answers: InitialAnswers):
    options = {question.id: question.options for question in QUESTIONS.questions}
    try:
        answers.validate_options(options)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class RoadmapRequest(BaseModel):
    confirmed: bool
    goal: ShortText
    answers: InitialAnswers
    follow_up_answers: dict[Literal["follow_up_1", "follow_up_2"], ShortText] = Field(default_factory=dict)
    samples: list[dict] = Field(min_length=2, max_length=3)


@app.post("/v1/onboarding/roadmap")
def onboarding_roadmap(request: RoadmapRequest):
    validate_answers(request.answers)
    answers = request.answers
    profile = {
        "motivation": [answers.other_details.get("motivation", value) if value == "Other" else value
                       for value in answers.motivation],
        "goals": [answers.other_details.get("outcomes", value) if value == "Other" else value
                  for value in answers.outcomes],
        "challenges": [answers.other_details.get("challenges", value) if value == "Other" else value
                       for value in answers.challenges],
        "situations": [answers.other_details.get("situation", answers.situation), answers.situation_details],
        "priority": (answers.other_details.get("outcomes" if "Other" in answers.outcomes else "challenges")
                     if answers.priority == "Other" else answers.priority),
        "follow_up_answers": request.follow_up_answers,
    }
    return generate_roadmap(Onboarding(confirmed=request.confirmed, goal=request.goal,
                                      profile=profile, samples=request.samples),
                            include_experimental=True)

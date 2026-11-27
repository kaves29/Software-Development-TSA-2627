# Speakly backend

This is the first slice of the stateless onboarding prototype. It provides a health check and a versioned set of initial questions.

From the repository root, create a virtual environment, install dependencies, and start the service:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

GET /health returns `{"status":"ok"}`. GET /v1/onboarding/questions returns the question set and its version. Interactive API documentation is available at /docs on the running server. For Other selections, the client should allow short free text. The priority options come from the selected outcomes and challenges. The client retains answers; these endpoints do not collect or save them.

Profile confirmation, the reviewed activity catalog, and roadmap generation are still to be implemented.

## Follow-up questions

POST /v1/onboarding/follow-ups accepts the initial answers and returns two single-select questions with an Other option. The client keeps the answers and sends them on each request. Example:

```json
{
  "question_version": "1",
  "name": "Sam",
  "age": 16,
  "language": "English",
  "motivation": ["Do better at school"],
  "outcomes": ["Explain ideas clearly"],
  "challenges": ["I lose my train of thought"],
  "situation": "Giving a presentation",
  "situation_details": "",
  "priority": "Explain ideas clearly",
  "other_details": {}
}
```

When a selection is Other, put its explanation in `other_details` using its question ID as the key. The priority must match a selected outcome or challenge. If Other is selected in both lists, choose an unambiguous priority. Free-text answers should omit personal and medical details.

Set `OPENAI_API_KEY` securely in the server environment to generate follow-ups. `OPENAI_MODEL` can override the default `gpt-4o-mini`. The backend excludes the name and exact age from the model request. This request sends the remaining supplied answers to OpenAI. Review privacy and age policies before use with real users.

Invalid answers return HTTP 422. Missing provider configuration or a provider failure returns HTTP 503 with a safe error. The service does not save answers. A client should allow a retry if generation fails. The model output is validated for two distinct questions with distinct choices, including Other.

For development tests, install pytest and httpx into the virtual environment and run `python -m pytest backend/tests -q`. Tests use a simulated provider and do not need an API key. Profile confirmation, the researched activity catalog, and roadmap generation remain to be built.

# Speakly backend

This is the first slice of the stateless onboarding prototype. It provides a health check and a versioned set of initial questions.

From the repository root, create a virtual environment, install dependencies, and start the service:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

GET /health returns `{"status":"ok"}`. GET /v1/onboarding/questions returns the question set and its version. Interactive API documentation is available at /docs on the running server. The client retains answers; these endpoints do not collect or save them.

Adaptive follow-ups, profile confirmation, the reviewed activity catalog, roadmap generation, and provider integration are still to be implemented.

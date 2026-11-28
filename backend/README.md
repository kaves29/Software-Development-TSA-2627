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

## Analyze an onboarding recording

POST /v1/onboarding/recordings/analyze accepts multipart form data with `recording` (an audio file or video file containing audio), `sample_id` (a distinct ID chosen by the client), `prompt` (the speaking prompt), and `media_type` (`audio` or `video`). Submit each of the two or three samples separately. The response has the form `{"id": "sample-1", "result": {...}}`, matching one entry in the existing roadmap prototype's `samples` list. The client keeps the responses for the later handoff.

The server temporarily writes the recording while analyzing it and removes the temporary file after the request, including on failure. Recordings are limited to 50 MB and the audio pipeline accepts up to 240 seconds. Errors return 413 for oversized recordings, 422 for empty or unprocessable recordings, and 503 when analysis is unavailable.

Recording analysis needs ffmpeg and the dependencies in `speech_analysis/requirements.txt`, in addition to the main backend requirements. Set `SPEAKLY_MODEL_CACHE` to a writable model cache if needed. The first run may download upstream models. `SPEAKLY_WHISPER_MODEL` selects the Whisper model and defaults to `small.en`. To use the research filler classifier, securely provision its checkpoint outside Git and set `SPEAKLY_FILLER_HEAD` to its path. Without that checkpoint, the audio pipeline still returns its other available measurements. Video additionally needs `speech_analysis/requirements-video.txt` and `SPEAKLY_POSE_MODEL` pointing to a locally provisioned MediaPipe pose model. The video path currently uses pose analysis only.

The trained filler checkpoint and video analysis remain experimental. Mock-based API tests verify data flow and cleanup, but a real recording and model run has not yet been verified through this endpoint. Results should be presented as limited observations, not diagnoses.

## Test the backend in VS Code

Open the repository folder in VS Code and open a terminal. From the repository root, create a virtual environment and install the backend dependencies:

```sh
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS or Linux, or `.venv\\Scripts\\Activate.ps1` in Windows PowerShell. Then run:

```sh
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/test in your browser. The page checks the server, displays onboarding questions, sends editable sample answers to the follow-up endpoint, and uploads an audio or video file for analysis. It displays the response or error from the backend. Follow-ups need `OPENAI_API_KEY`, and recording analysis needs the additional models and dependencies described above. The page uses a sample profile and does not store answers in the browser.

## Test in Google Colab

Open [the Colab notebook](https://colab.research.google.com/github/kaves29/Software-Development-TSA-2627/blob/main/backend/test_ui/colab_backend_test.ipynb) and choose **Runtime → Run all**. The notebook clones this repository and starts the backend in a temporary Google Colab session, then displays the test page in the notebook. Use sample information. Follow-up generation requires an API key, and recording analysis requires the separate models and dependencies described above.

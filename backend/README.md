# Speakly backend

This API runs the stateless onboarding flow from questions through recording analysis to a practice roadmap.

From the repository root, create a virtual environment, install dependencies, and start the service:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

GET /health returns `{"status":"ok"}`. GET /v1/onboarding/questions returns the question set and its version. Interactive API documentation is available at /docs on the running server. For Other selections, the client should allow short free text. The priority options come from the selected outcomes and challenges. The client retains answers; these endpoints do not collect or save them.

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

For development tests, install pytest and httpx into the virtual environment and run `python -m pytest backend/tests -q`. Tests use a simulated provider and do not need an API key.


## Recording analysis and roadmap

Install FFmpeg and the audio dependencies with `python -m pip install -r backend/speech_analysis/requirements.txt`. For video, also install `backend/speech_analysis/requirements-video.txt` and set `SPEAKLY_POSE_MODEL` to a MediaPipe Pose Landmarker task file. Optional `SPEAKLY_MODEL_CACHE` points to the Whisper checkpoint directory and `SPEAKLY_WHISPER_MODEL` selects an English checkpoint. The default is `small.en`.

POST `/v1/onboarding/recordings` as multipart form data with `file`, optional `prompt`, and `video=true` for video analysis. Each upload can be up to 80 MiB and four minutes. Analysis runs locally and temporary uploads are removed afterward. Keep the returned `{id, result}` objects on the client.

POST `/v1/onboarding/roadmap` with the following JSON fields:

| Field | Value |
|---|---|
| `confirmed` | `true` after the user confirms the profile |
| `goal` | The chosen speaking goal |
| `answers` | The same initial answers used for follow-ups |
| `follow_up_answers` | Optional selections keyed by `follow_up_1` and `follow_up_2` |
| `samples` | Two or three objects returned by recording analysis |

The roadmap request sends the confirmed practice profile and numeric or boolean observations to OpenAI. The request uses ordinal sample numbers and excludes raw media, transcripts, names, and exact ages. Experimental observations are marked as such. The response contains ten weekly themes and seven ten-minute activities for the first week. With no server API key the roadmap endpoint returns HTTP 503.

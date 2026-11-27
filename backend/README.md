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

The endpoint currently returns deterministic **mock** questions based on the supplied challenges. It does not contact OpenAI, even when `OPENAI_API_KEY` is present. The future `openai_followups` adapter defaults to `gpt-5.4-mini` and excludes name, exact age, and question version from its provider input, but it is deliberately not connected to the endpoint. No live provider was tested in this integration.

Invalid answers return HTTP 422. The service does not save answers. Questions are validated for two distinct IDs, distinct prompts and choices, including Other. The mock demonstrates the contract; it is not a personalized LLM interview.

For development tests, install pytest and httpx into the virtual environment and run `python -m pytest backend/tests -q`. Tests use a simulated provider and do not need an API key.


## Recording analysis and roadmap

Install FFmpeg and the audio dependencies with `python -m pip install -r backend/speech_analysis/requirements.txt`. `SPEAKLY_WHISPER_MODEL` selects an English checkpoint (default `small.en`), and `SPEAKLY_MODEL_CACHE` selects its cache directory. Set `SPEAKLY_FILLER_HEAD` to the trained research checkpoint to enable the WavLM filler model; the compatible WavLM encoder also needs to be available in the Hugging Face cache or downloaded according to its terms. The checkpoint is stored separately in the private research workflow, not in this repository; see `agent-context/backend/AI/Sherria Codex pickup.md` and `audio-analysis.md`. Without a configured checkpoint, filler events come from a transcript heuristic, identified by `features.fillers.method`; a checkpoint failure appears in `quality.errors`. A configured but missing checkpoint returns 503.

For video, install `backend/speech_analysis/requirements-video.txt` and set `SPEAKLY_POSE_MODEL` to a MediaPipe Pose Landmarker task file. `SPEAKLY_HAND_MODEL` and `SPEAKLY_FACE_MODEL` are optional. Set `SPEAKLY_POSE_FINGERTIP_PROXIMITY=1` only to opt into the experimental pose-fingertip proximity calculation. All movement features remain experimental. The evaluator does not diagnose medical conditions or establish nervousness. Its benchmark limitations and research-only data/model terms are in `audio-analysis.md`.

POST `/v1/onboarding/recordings` as multipart form data with `file`, optional `prompt`, and `video=true` for video analysis. Each upload can be up to 80 MiB and four minutes. Analysis runs locally and temporary uploads are removed afterward. Keep the returned `{id, result}` objects on the client.

The latest main-branch contract is also supported: POST `/v1/onboarding/recordings/analyze` with multipart `recording`, `sample_id`, `prompt`, and `media_type` (`audio` or `video`). This route preserves the supplied ID and accepts up to 50 MiB. Both routes use the same analysis pipeline and response shape.

POST `/v1/onboarding/roadmap` with the following JSON fields:

| Field | Value |
|---|---|
| `confirmed` | `true` after the user confirms the profile |
| `goal` | The chosen speaking goal |
| `answers` | The same initial answers used for follow-ups |
| `follow_up_answers` | Optional selections keyed by `follow_up_1` and `follow_up_2` |
| `samples` | Two or three objects returned by recording analysis |

The roadmap combines the confirmed profile, follow-up answers, and two or three sample results using the existing session and evidence handoff. The default generator is a deterministic mock, identified by `generation_mode: "mock"`; it makes no OpenAI request. It returns ten broad weekly themes and seven ten-minute activities for the first week from the seed catalog. The future provider input uses ordinal sample numbers and omits raw recordings, transcripts, names, and exact ages; free-text answers can themselves contain identifying information. Experimental observations are marked as such and are not diagnoses. The retained `openai_roadmap` adapter defaults to `gpt-5.4-mini` but requires deliberate future integration and verification before live use.

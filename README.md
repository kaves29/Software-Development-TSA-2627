# Speakly

Personalized communication practice · TSA Software Development 2026–2027

Speakly is a planned web app for practicing presentations, interviews, and everyday conversations. Users record a response, review feedback, and get a focused exercise based on their goals and previous attempts.

The goal is to make useful speaking practice easier to access without needing a coach or someone available to listen every time.

## Project status

This project is in the planning stage. The features and technology choices below describe the proposed app; they have not been implemented yet. **Speakly** is the working title.

## How it works

1. **Choose a goal.** Pick a practice mode and something to work on, such as pacing or giving shorter answers.
2. **Record a response.** Answer a prompt using audio, with optional webcam recording for movement feedback.
3. **Review feedback.** See the transcript and supported measurements, such as speaking pace, pauses, and filler-word frequency.
4. **Try a targeted exercise.** Get an activity selected from your goals and session results.
5. **Practice again.** Compare similar attempts and track progress over time.

## Planned features

### Practice modes

- **Presentations:** Practice explaining a topic, organizing ideas, and managing pace.
- **Interviews:** Work through practice questions and develop relevant, concise answers.
- **Everyday communication:** Practice explaining ideas and responding to conversational prompts.
- **Fluency practice:** Choose supportive speaking exercises and work at your own pace.

### Speech feedback

Transcription will support feedback on speaking pace, pauses, and repeated filler words where the recording and provider data allow reliable measurements. Users can also review their transcript to spot unclear explanations or long responses.

### Personalized exercises

The recommendation engine is the core of the project. It will use the user's chosen goals, available metrics, and practice history to suggest what to work on next. The first version will use rules we write and test ourselves.

For example, someone working on interview pacing could record an answer, review their pace, and receive a short follow-up exercise before trying a similar question again.

### Progress tracking

A dashboard will show session history, completed exercises, and changes in individual metrics across comparable attempts. Progress will be tied to personal goals rather than a single overall speaking score.

### Optional movement feedback

Webcam-based pose estimation could help users review repeated upper-body movement during presentation practice. This feature will be optional, and the main practice workflow will work without a camera.

## Proposed technology

| Component | Proposed tools |
| --- | --- |
| Frontend | React, HTML, and CSS |
| Backend | Python and FastAPI |
| Speech recognition | A speech-to-text provider, still to be selected |
| Speech metrics and exercise recommendations | Custom Python logic |
| Movement tracking | MediaPipe or a similar pose-estimation tool |
| Data storage | SQLite initially; PostgreSQL if needed |
| Optional prompt generation | An LLM API |

Existing tools will handle transcription and pose estimation. Our work will focus on the practice workflow, metric calculations, exercise selection, progress tracking, and interface. Provider choices will depend on accuracy, cost, and privacy requirements.

## Accessibility and privacy

- Let users choose their goals and practice without a webcam.
- Support keyboard navigation, readable text, written prompts, and transcripts where available.
- Describe observable speech and movement patterns without judging confidence, intelligence, or competence.
- Explain transcription limitations, including differences caused by accents and recording conditions.
- Avoid retaining raw recordings by default, and require explicit consent when storage is needed.
- Give users control over saved session history and keep API credentials secure.

Speakly is a practice tool. It will not diagnose or treat speech disorders.

## Development plan

1. Build goal selection, prompts, and audio recording.
2. Add transcription and speech metrics, including handling for failed recordings and API requests.
3. Implement the exercise recommendation engine.
4. Save session history and build the progress dashboard.
5. Add optional webcam movement feedback.
6. Test accessibility, error cases, and usability; prepare project documentation and a demo.

The first milestone is a complete audio-only practice session: choose a goal, record an answer, review feedback, and try a recommended exercise.

## Testing

We plan to test metric calculations, exercise selection, session storage, and failures such as missing audio, denied camera access, and unavailable APIs. Voluntary usability testing will help us check whether the feedback is understandable and the exercises are useful. Any results will include the study's size and limitations.

## Post-assessment frontend prototype

From the repository root, run:

```sh
python -m http.server 8000 --directory frontend
```

Open http://localhost:8000. The prototype opens on the post-assessment
dashboard. Choose **Presentation** to set a format, duration, prep time,
and audience, with an optional local PDF. Choose **Interview** to practice
with a built-in or self-entered question. Each session has a timer and a
completion screen with options to retry or return home.

The prototype uses HTML, CSS, and JavaScript without external dependencies.
It can be served locally for offline review and leaves the production client
choice open. Rehearsals are timed locally, slides stay on the device, and
the session summary shows elapsed time. Assessment, account services,
recording, analysis, saved sessions, and Roadmap are outside this prototype.

The screens draw on the team’s [FigJam app flow](https://www.figma.com/board/fbmVOq5zpYMDSyR7gGmH9z/app-flow)
and the supplied Cube and Spot palettes. See the [project status](agent-context/project/md/project_status.md#frontend-implementation-progress)
for implementation and verification details.

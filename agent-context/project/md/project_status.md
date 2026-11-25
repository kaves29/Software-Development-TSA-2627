# Project status and decisions

## Current state

- Working title: Speakly. The original concept also used SpeakWise; the README uses Speakly consistently.
- Stage: browser practice prototype plus an initial audio/video analysis and roadmap API prototype. The Python CLI and research trainer live in `backend/speech_analysis/`; see [audio analysis and filler research](../../backend/AI/audio-analysis.md) for design and verified results. The browser interface is not yet connected to the AI service.
- Completed: a public project overview and agent context structure, including roles, coding standards, competition notes, a deadline tracker, and synchronized agent guides.
- The audio analyzer has passed CPU smoke checks. The experimental filler classifier completed private Kaggle training and held-out podcast evaluation, without meeting the generalization target. Validation on real onboarding responses and integration with the practice interface and roadmap generator remain future work.

## Proposed product

Users choose a communication goal, record a response, review supported speech metrics, receive a targeted exercise, and compare similar attempts. Planned modes include presentations, interviews, everyday communication, and user-selected fluency practice. Movement feedback is optional. Avoid inferring personal traits from speech or posture or claiming to diagnose speech disorders.

The initial concept proposes an audio-only end-to-end milestone before movement tracking. This is a proposal for team review, not agent authorization to select priorities or start implementation.

## Technology choices awaiting confirmation

The user explicitly confirmed that React Native and Supabase remain proposals; do not treat their role assignments as technology approval.

| Topic | Earlier concept / README | Later role notes | Status |
| --- | --- | --- | --- |
| Client | React web app | React Native frontend responsibility | Unresolved; ask the team before implementation. |
| Database | SQLite initially, potentially PostgreSQL | Supabase/SQL responsibility | Unresolved; ask the team before implementation. |
| Backend | Python and FastAPI | No replacement specified | Proposed, not confirmed. |
| Speech / pose / generative AI | Provider undecided; MediaPipe suggested for pose | Research responsibilities assigned | No provider selected. |

## Open project decisions

- Confirm platform/framework, database, and implementation scope with the team.
- Competition year: 2026–2027, confirmed by the user. The supplied excerpts carry a 2027 & 2028 printed label; preserve that source label without using it as the project year. Competition level, official theme, exact deadline, and any current clarifications still need verification.
- Determine the competition submission's treatment of identifying context. Supplied rules restrict identifying information, while these requested notes contain names and location. Do not publish a competition submission without resolving this with the team/advisor.
- Assign a submission captain and select up to three presenters when appropriate; agents must not choose them.

## Documentation practice

Update this file when the overall state or an unresolved decision changes. Store detailed frontend/backend decisions in their area's `md/` folder when established, and link them from the area's guide. Do not create speculative methodologies or skill instructions. Preserve evidence of external resources and AI assistance for the required reflection without claiming the reflection is complete.

## UI concept progress

- 2026-11-24: Generated a first static Speakly concept for team review, covering practice mode selection, interview recording with camera off, and feedback with a next exercise. Used the repository's proposed practice flow. The Figma app flow file link was unavailable, so screen order and wording remain provisional.
- Used the user-supplied Cube and Spot palette images. The concept uses very light sage as the app background, slate navy for primary actions, and Spot colors in small accents.
- AI use for reflection: Codex ImageGen produced the concept image. The displayed session metrics are fictional and should be visibly labeled as sample data in future design reviews. The requested design and motion skills were unavailable in this session. No implementation work was started.

- 2026-11-24: Read the [FigJam app flow](https://www.figma.com/board/fbmVOq5zpYMDSyR7gGmH9z/app-flow) and used Codex ImageGen to draft two static review boards with six screens: goal selection, placement test introduction, home, presentation setup, mock interview setup, and personalized roadmap. Used the supplied Cube and Spot palettes. The dashboard percentage and roadmap progression are illustrative. The presentation draft shows an unsupported 10-minute prep setting and conflicting mode selections. The board specifies prep choices of none, 30 seconds, 1 minute, and 3 minutes. No app implementation started.

## Frontend implementation progress

- 2026-11-24: Added a dependency-free browser prototype for the approved post-assessment scope. The dashboard leads to the Presentation and Interview setup screens from FigJam. No production framework decision was made.
- Presentation supports random topics, prepared presentations, and assignments. The team’s specified presentation and prep times are available. A selected PDF opens through a local browser URL. Practice distinguishes prep, remaining time, and overtime.
- Interview uses a built-in sample question or a user-entered question, with an elapsed timer. Both flows offer a completion screen with retry and home links. No recording, analysis, or results storage is involved.
- Verified in Chromium at 360 px: dashboard navigation, both setup-to-completion paths, whitespace validation, creation of the local PDF link, early end of prep, retry, return home, and no horizontal overflow or uncaught page errors. PDF rendering and the natural countdown transitions were outside this check.
- AI use for reflection: Codex assisted with the frontend code, documentation, and browser verification. The earlier concept boards were generated with ImageGen. Team review of the interface and rehearsal behavior remains pending.

- 2026-11-25: Reworked Home into one phone dashboard based on the user's final stacked layout. Added a sticky goal area with an editable date and display name, an overlapping practice panel, and a fixed Home, Presentation, Interview, Roadmap tab bar. The active tab purple was visually matched to the supplied reference.
- Added a lightweight Roadmap with local focus selections and self-reported skill improvements. Progress counts distinct device-local dates on which a rehearsal was finished. Recording count stays at zero while capture is unavailable. Browser storage holds preferences and practice dates without an account or backend.
- Verified in Chromium at 360 × 640: fixed nav during scroll, sheet overlap, no horizontal overflow, date persistence after reload, display name, Roadmap navigation and improvement display, both rehearsal paths, and same-day deduplication. No uncaught page errors.
- 2026-11-25: Expanded the browser presentation setup with editable category-based sample topics, difficulty, and presentation style from the supplied FigJam screenshot. The rehearsal remains a timer with optional local PDF viewing; recording, AI-generated topics, slide analysis, and automated feedback are not implemented. Codex assisted with implementation and browser verification.
- 2026-11-25: Added optional browser microphone recording to presentation practice, including a recording indicator and session playback. Recording remains in browser memory and is released when leaving the session. Codex assisted with implementation and browser verification.

- 2026-11-25: Combined the shared skills update, Playwright skill, and Sophie's presentation recording branch. Presentation audio can be recorded with microphone permission and reviewed at session completion. It is not saved across sessions. Chromium verification used a simulated microphone and confirmed recording controls and playback element. The dashboard counts saved recordings, currently zero.

# Project status and decisions

## Current state

- Working title: Speakly. The original concept also used SpeakWise; the README uses Speakly consistently.
- Stage: planning and an initial audio analysis prototype. The Python CLI and research trainer live in `backend/speech_analysis/`. See [audio analysis and filler research](../../backend/AI/audio-analysis.md) for design and verified results.
- Completed: a public project overview and agent context structure, including roles, coding standards, competition notes, a deadline tracker, and synchronized agent guides.
- The audio analyzer has passed CPU smoke checks. The experimental filler classifier completed a private Kaggle training and held-out podcast evaluation. Validation on real onboarding responses and integration with the mobile app and roadmap generator remain future work.

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

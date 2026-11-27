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

## Backend implementation progress

- 2026-11-27: Started the approved FastAPI onboarding prototype. Added a health endpoint and versioned initial-question endpoint. Adaptive follow-ups, profile confirmation, researched activity catalog, roadmap generation, and OpenAI integration remain to be built.
- 2026-11-25: Expanded the browser presentation setup with editable category-based sample topics, difficulty, and presentation style from the supplied FigJam screenshot. The rehearsal remains a timer with optional local PDF viewing; recording, AI-generated topics, slide analysis, and automated feedback are not implemented. Codex assisted with implementation and browser verification.
- 2026-11-25: Added optional browser microphone recording to presentation practice, including a recording indicator and session playback. Recording remains in browser memory and is released when leaving the session. Codex assisted with implementation and browser verification.

- 2026-11-25: Combined the shared skills update, Playwright skill, and Sophie's presentation recording branch. Presentation audio can be recorded with microphone permission and reviewed at session completion. It is not saved across sessions. Chromium verification used a simulated microphone and confirmed recording controls and playback element. The dashboard counts saved recordings, currently zero.

- 2026-11-25: Refined the mobile home dashboard with a pale sage goal area, updated countdown ring, clearer stacked practice links, softer scrolling panel, and purple active navigation. Kept existing goal, practice, roadmap, and progress behavior. Frontend Design and Unslop Motion informed the visual treatment. Chromium checks at 320 px and 390 px covered goal-date entry, navigation to Presentation, Interview, and Roadmap, overflow, and page errors. Changes await user approval before GitHub push.
- 2026-11-25: Added a Monday-to-Sunday dashboard strip showing actual completed rehearsal days and highlighting today, with accessible day descriptions. Updated the app-wide font stack and used serif headings in the practice panel, guided by the supplied mobile reference and UI/UX Pro Max, Frontend Design, and Unslop Motion. Chromium checks at 320 px and 390 px covered completion, persistence after reload, goal date, reduced-motion setting, and overflow. Changes are local pending push approval.
- 2026-11-25: Updated the dashboard with a muted navy-to-sage upper background and a light scrollable session panel. Starts with two editable sessions, allows up to five, and stores names, types and descriptions in the browser. Session editor saves on dismissal and supports deletion. Bottom navigation still provides access to the practice screens. Verified the session limit, editing and reload persistence, deletion, mobile overflow and fixed navigation in Chromium at 360 px. Session types are planning labels and do not launch a practice automatically.

- 2026-11-25 9:51 PM Eastern: Sri directed the dashboard layout, color transition, weekly practice display, and editable session planner. Codex implemented and tested the changes with Sri's guidance; the frontend design, UI/UX, and motion skills informed the work. Sri approved pushing this batch to GitHub.

- 2026-11-25 9:53 PM Eastern: Sri requested contributor names and timestamps for future progress and change entries. Codex updated the shared agent guides to record the responsible person, time zone, and AI assistance when applicable.

- 2026-11-25 10:12 PM Eastern: Sri directed a dashboard update with a glowing countdown, up to three goals, date-based session planning, completion checks, optional session times, a calendar, and editable self-reported skill bars. Codex implemented the changes and verified goal creation/reset, task completion, time display, date navigation, skill edits, persistence, and mobile overflow in Chromium. Changes await push approval.
- 2026-11-25 10:17 PM Eastern: Sri requested Cube navy navigation, a subtle fade beneath the bottom bar, a hidden mobile scrollbar, and a dash for an unset goal. Codex updated the mobile styles and verified the empty goal, scrolling, scrollbar styling, navigation color, and mobile width in Chromium.
- 2026-11-25 10:18 PM Eastern: Sri approved publishing the dashboard updates and contributor-and-timestamp documentation rule. Codex prepared the approved changes for the shared main branch.
- 2026-11-25 10:28 PM Eastern: Sri requested calendar and navigation icons, outside-click calendar dismissal, noninteractive zeroed skill bars, a serif goal number, and a shared time-line for sessions with matching times. Codex implemented the refinements and verified dismissal, grouped times, zero bars, persistence and mobile width in Chromium. Existing saved skill names and values remain in browser storage; the current display shows zero pending a measured progress source.
- 2026-11-25 10:33 PM Eastern: Sri requested a cleaner goal glow and more polished session and date-picker interfaces. Codex refined the circle and modal styles and connected goal and session date fields to the shared calendar. Frontend Design and UI/UX Pro Max informed the changes. Chromium verification covered both nested date pickers, save and reload, Escape, mobile width, and a visual review. Changes await push approval.
- 2026-11-25 10:35 PM Eastern: Sri requested centered goal settings and cleaner, initially blank time controls. Codex centered the goal editor and added a styled hour, minute, and AM/PM picker with clearing. Chromium verification covered empty times, PM selection, saved values, clearing, the goal calendar, and mobile width. Changes await push approval.
- 2026-11-25 10:37 PM Eastern: Sri requested consistent calendar and session typography and restrictions on changing past sessions. Codex updated the styling and made past sessions view-only, disallowed assigning a session to a past date, and retained calendar navigation to past dates. Chromium checks used fixed local dates to verify past, current, and future behavior and preservation of existing sessions. Changes await push approval.
- 2026-11-25 10:38 PM Eastern: Sri approved publishing the calendar, session, goal, typography, and progress-bar refinements. Codex prepared the tested batch for the shared main branch.

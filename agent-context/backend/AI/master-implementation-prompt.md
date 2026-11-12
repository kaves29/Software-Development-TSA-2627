# Master implementation prompt: AI onboarding and personalized roadmap

Give this entire prompt to the implementation agent. It defines the approved prototype scope and decisions from the project owner. Follow the repository's root and backend `AGENTS.md` instructions and coding rules before changing code.

## Mission

Implement the backend AI onboarding and personalized roadmap prototype for Speakly in the existing repository. The prototype must collect a focused learner profile, ask a small number of useful adaptive follow-up questions through the OpenAI API, let the user confirm a concise profile summary, and generate a personalized ten-week speaking-practice roadmap.

This is backend and AI logic work only. The team's other members own the React Native interface. Build a clear HTTP API contract that a React Native client can call, but do not build screens, navigation, styling, or mobile UI. Do not add speech recognition, audio analysis, camera processing, posture analysis, progress tracking, or authentication. Do not persist onboarding responses or generated roadmaps. The user-facing prototype should end when it returns the generated roadmap.

## Repository-first procedure

1. Inspect the current checkout, all applicable `AGENTS.md` files, project status, coding rules, existing source, dependencies, and test setup before choosing file locations or adding dependencies.
2. The repository may still be planning-only. If so, create only the minimal backend structure needed for this API, using the existing project conventions where available.
3. Do not overwrite existing work or treat proposed technologies in old notes as approved unless this prompt approves them. Python with FastAPI is approved for this prototype.
4. Keep tracked project files focused. Update relevant backend documentation indexes if adding documentation. Keep paired `AGENTS.md` and `CLAUDE.md` files byte-for-byte identical if either is changed.
5. Explain any conflict between this prompt and current code or project notes before making a consequential change. Routine implementation choices can be made independently and documented in the final handoff.

## Approved product decisions

- Audience: general English-speaking people who want to improve everyday speaking and presentations, including skills such as managing ordinary speaking nerves, projecting the voice, articulation, pacing, organizing ideas, engaging listeners, and body language.
- Practice language: English only in this prototype. Other languages are future work.
- Collect age during onboarding as a numeric age or age field, but do not request birth date. Keep the entered value in the app's onboarding state. Send only a coarse age band to the model when it is needed to make lesson wording age-appropriate. Do not add an age gate in this prototype; the project owner will decide age policy later.
- Do not ask users to disclose diagnoses, mental disorders, medical history, or other unnecessary sensitive information. Ask about speaking situations, self-described challenges, goals, and preferences instead. Never diagnose or imply that the model can assess a disorder.
- The first question round is structured: mostly selectable options, including multi-select where appropriate, plus optional short text for nuance. Use concise, understandable labels. Include an “Other” or equivalent free-text path where appropriate.
- Gather the information that makes a roadmap personal: specific speaking situations, top struggles, desired outcomes, practice constraints, and learning preferences. Initial questions should also establish the user's speaking goal, English practice context, age, and commitment of ten minutes each day.
- After the initial answers, ask no more than two adaptive follow-up rounds, with no more than three questions per round. Ask only questions whose answers could change the roadmap. Avoid repeating information already supplied. Stop early when sufficient information is available.
- After follow-ups, summarize the learner profile in plain language and require the user to confirm or edit it before roadmap generation. The service is stateless, so the client sends accumulated answers and confirmation in requests; do not store session data server-side.
- Generate a ten-week roadmap at ten minutes per day, seven days each week. Organize it into ten progressive weekly stages with reusable daily activity types, not 70 individually authored lessons.
- Use a common speaking-skills progression as a flexible backbone: baseline/goals; nerves and preparation; breathing and projection; articulation and pace; organizing ideas; clear explanations; audience engagement; body language; impromptu practice; integrated presentation. Do not force every learner through an identical sequence.
- Personalize the early roadmap deeply around the user's chosen goals and weak areas, spending more time and practice on those skills. Use approximately the final one and a half weeks for broadly useful speaking skills, as requested. Adapt the route, emphasis, and repetition to the user while retaining a coherent progression.
- The current prototype ends at roadmap generation. It does not track mastery. Future versions may use user self-checks and completed practice activities, and later real speech-analysis APIs; those are out of scope now.
- Use a small seed catalog of reviewed activity types and lesson patterns. The model may select, adapt, sequence, and explain these; it must not invent an unrestricted curriculum or present generic filler as personalization.
- Research high-quality public speaking and communication-learning roadmaps from credible internet sources before defining the seed catalog. Prefer reputable educational, academic, professional communication, and evidence-based sources. Keep a concise source register with title, organization/author, URL, publication date when available, and the specific lesson-design idea supported. Distinguish evidence-backed guidance from product design choices. Do not copy proprietary course text. If a claim cannot be verified, omit or label it as a design hypothesis.
- Do not modify or build the React Native frontend. Provide endpoint definitions, request/response schemas, and example payloads so the frontend team can integrate separately.

## AI and service architecture

- Use Python and FastAPI for the backend prototype.
- Make OpenAI API calls from the backend only. The mobile client must never receive the OpenAI secret or call the provider directly.
- Read the API key from an environment variable named `OPENAI_API_KEY`; never hard-code it, write it to a tracked file, print it, include it in errors, or return it from an endpoint. Provide a safe `.env.example` only if consistent with repository conventions, containing a placeholder and no secret.
- Keep provider/model selection configurable through a non-secret environment variable if useful. Select a currently supported, cost-conscious model suitable for structured text generation, verify its current official API docs, and document the choice and date. Do not claim a model is trained or specialized by Speakly.
- Use the official OpenAI API and SDK documentation current at implementation time. Use structured output/schema-constrained responses when supported by the selected model and endpoint; otherwise validate responses with Pydantic and handle malformed output explicitly.
- Treat the model as a constrained question-generation and roadmap-personalization layer, not the authority on speech science. Give it the approved question/lesson catalog, user answers, schedule, and relevant source-derived notes. Require it to stay within those inputs and return the exact response schema.
- Validate all model outputs server-side. Reject or repair invalid shapes with a bounded retry; never silently accept malformed content or loop indefinitely. If generation remains invalid, return a useful, non-sensitive error and preserve a usable retry path.
- Set request timeouts and handle provider timeouts, rate limits, unavailable service, invalid credentials, and malformed responses with safe errors. Do not expose provider internals or user content in logs. Do not log secrets or full onboarding payloads.
- Keep the API stateless. Do not add a database, user account system, file storage, or server-side history.
- Minimize provider inputs: do not send direct identifiers; send only relevant answers and the coarse age band when age affects age-appropriate phrasing. Do not send raw audio, images, or video.
- Add a clear note in backend docs that third-party API processing is involved and privacy/age policy needs team review before real deployment, especially because the product may have younger users. Do not block the prototype with a new age-gate decision.

## API behavior and integration contract

Inspect repository conventions and choose sensible route names, but provide equivalent capabilities to these operations:

1. **Initial onboarding metadata/questions:** Return the fixed, versioned question set and selectable options to the client. Questions must cover goals, speaking situations, self-rated challenges, daily practice constraints/preferences, English context, and age. Use multi-select where suitable and short optional free text for nuance. Do not make an LLM call to generate this first round.
2. **Adaptive follow-up generation:** Accept the structured initial answers plus prior follow-up questions and answers. Return zero to three concise, relevant questions and a completion indicator. Enforce a maximum of two rounds on the server, not only in UI logic. Include stable question IDs and answer-type/options metadata. If sufficient information already exists, return no more questions.
3. **Profile summary:** Given the accumulated answers, return a concise, editable learner-profile summary and the key goals/challenges/constraints that will drive the roadmap. The client must be able to send user-confirmed or edited summary content back before roadmap creation.
4. **Roadmap generation:** Accept confirmed profile, approved catalog/version, and schedule. Return a validated ten-week roadmap. Each week has a week number, theme, personalized rationale, weekly outcome, and seven daily activities. Each daily activity should fit a ten-minute session and include a title, duration, activity type from the seed catalog, concise instructions, and a reflection/self-check prompt where suitable. Ensure total schedule is ten weeks × seven days × ten minutes; do not claim the user mastered a skill.
5. **Health check:** Provide a minimal health endpoint that reports service availability without revealing configuration secrets.

Document exact route paths, HTTP methods, request/response schemas, validation behavior, error codes, and at least one full example from initial answers through follow-up, profile confirmation, and roadmap response. Use consistent versioning if appropriate. Keep schemas understandable to frontend teammates.

Because the service is stateless, define client-supplied state explicitly: the mobile client retains onboarding answers, returned question IDs, answers, and confirmed profile in memory or its own storage policy. The backend must not assume hidden conversation history. A request must contain enough context to produce its response.

## Roadmap personalization and quality rules

- Make each roadmap visibly specific to the user's chosen situations, top struggles, outcomes, available practice time, and learning preferences. Explain briefly why each weekly focus was selected.
- Use the user's own non-sensitive wording where helpful, without parroting private details unnecessarily.
- Prioritize selected weaknesses and goals during the first approximately eight and a half weeks. Use the final one and a half weeks for integration and broader skills that benefit most speakers. Convert the half-week into an explicit, coherent schedule across the final two weeks while keeping exactly 70 ten-minute days; document the chosen allocation.
- Reuse and vary reviewed activities (for example: short model/example, guided rehearsal, focused practice, reflection, scenario rehearsal, and integrated practice). Ensure activities advance in difficulty and do not repeat identical generic tasks merely to fill days.
- Account for the daily ten-minute limit. Avoid assigning tasks requiring unavailable APIs, other people, special equipment, video, or a camera. Body-language exercises may use self-observation and optional mirror practice, but must not claim automated visual assessment.
- Do not claim objective progress measurements or personalized diagnostics when no analysis is available. Distinguish user self-report from measured evidence.
- Use supportive, non-judgmental language. Avoid grading intelligence, personality, confidence, accent quality, disability, or mental health. Focus on observable skills and user-selected goals.
- Do not infer that an accent is a flaw. Articulation practice is about intelligibility and the user's own goals, not accent erasure.
- Do not promise that the roadmap will eliminate anxiety, stuttering, or other clinical symptoms. Keep ordinary presentation nerves framed as a common practice concern; do not provide diagnosis or treatment.
- Provide the user a way to revise onboarding answers and regenerate the roadmap. Do not imply the generated plan is immutable or guaranteed to work.

## Suggested seed catalog

Research and refine this before implementation. Keep it small and reviewable; each catalog entry should have an ID, skill area, learning objective, activity pattern, expected duration, difficulty range, accessibility variation, and source or design rationale.

Candidate skill areas and patterns:

- Goal and situation baseline: select a real speaking scenario and define one observable goal.
- Preparation and nerves: organize a short preparation routine; practice starting with a low-pressure first sentence.
- Breathing and projection: paced breathing for readiness and comfortable voice projection without strain.
- Articulation and pace: clarity, pauses, and deliberate pacing using a short text or self-chosen sentence.
- Organization: use a simple opening–point–example–close structure to make a response easier to follow.
- Clear explanation: explain one idea to a listener with a concrete example and plain language.
- Audience engagement: use a relevant hook, signposting, rhetorical question, or audience-aware example; avoid manipulative tactics.
- Body language: practice posture, gestures, and gaze awareness through optional self-observation; do not score appearance.
- Impromptu speaking: short responses using a simple planning structure.
- Integrated practice: combine selected skills in a brief presentation or everyday speaking scenario, followed by self-reflection.

The catalog is a scaffold, not an approved final curriculum. Keep any research-derived statement traceable to a source. If credible sources disagree, prefer modest, non-clinical guidance and note the uncertainty rather than asserting a universal method.

## Initial question design

Create a first-round questionnaire that is concise enough to complete comfortably. Use selectable and multi-select options plus optional short answers. At minimum cover:

- Age (numeric age only; do not ask birth date).
- Confirmation that practice is in English for this prototype (English is the only supported practice language).
- Speaking situations the user cares about (for example: presentations, class participation, interviews, conversations, explaining ideas).
- Goals the user wants to achieve.
- Self-identified speaking challenges (for example: getting started, organizing ideas, audibility/projection, articulation, pace, pauses, keeping attention, gestures/posture, ordinary nerves).
- Daily commitment, defaulted to ten minutes; the ten-week roadmap itself remains ten minutes daily.
- Learning preferences and practical constraints, including optional short text for context.

Do not ask about mental-health diagnoses, disability status, trauma, medication, or sensitive personal history. Optional text should include a reminder not to include medical or identifying information.

## Validation and acceptance criteria

Before completion, run the repository's relevant checks and add meaningful tests for the new API behavior. Do not alter unrelated tests or protected project decisions.

The prototype is acceptable when:

- A new developer can install dependencies and start the FastAPI service using documented commands and a placeholder environment file, without a real API secret being checked into source control.
- The service returns the fixed initial questions without calling OpenAI.
- A realistic sample profile produces useful adaptive questions; the server enforces at most three questions per round and at most two rounds and can stop early.
- A user can receive a profile summary, edit/confirm it, and request a roadmap.
- Roadmap output is schema-valid, exactly ten weeks, seven days per week, and ten minutes per day; it has personalized rationales and uses only approved activity types.
- The service does not persist onboarding data or roadmap output. Verify this from the implementation and tests.
- No OpenAI key or other secret is exposed to the client, logs, error responses, or repository.
- Provider failures and malformed model output return safe, documented errors.
- The React Native interface is not implemented or modified.
- Relevant tests pass, including tests for boundaries, insufficient answers, extra follow-up round attempts, user-edited profile, provider failure, invalid output, and the roadmap day/minute counts. Use a mock provider for deterministic tests; an explicit optional smoke test may exercise the live API only when credentials are configured.
- Any AI-generated curriculum content is constrained to the reviewed seed catalog; research notes cite sources and do not copy protected course content.

## Handoff

When implementation is done, report:

- What backend behavior and endpoints were added.
- The install and run commands and required environment variable names (never values).
- How the React Native frontend can call the service and carry state between requests.
- The seed catalog sources and which elements are evidence-informed versus design choices.
- Checks run and their actual results.
- Known limitations, including that speech/camera analysis, accounts, persistence, real mastery tracking, and other languages remain out of scope.
- Any follow-up decisions the team must make before real users, especially age/consent and privacy policy for third-party AI processing.

Do not claim the result is production-ready or scientifically validated merely because the API runs.

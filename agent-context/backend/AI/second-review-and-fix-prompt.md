# Second prompt: independently audit, test, and fix the AI onboarding prototype

Read the repository's root and backend `AGENTS.md` files and coding rules first. Then read `agent-context/backend/AI/master-implementation-prompt.md` as the product specification. Independently inspect the actual implementation in this checkout, compare it with the approved specification, run meaningful tests, fix verified defects within scope, and rerun the affected checks.

The task summary supplied outside the repository says five files were added and mentions Python/FastAPI/SQLite. Treat that summary as an unverified claim, not evidence. Confirm which files and implementation actually exist, where they are, what Git branch/commit is checked out, and whether the working tree contains changes. Do not assume a path on another computer is accessible. If implementation files are absent from this checkout, report that concrete blocker and do not invent test results or create a duplicate implementation.

## Audit requirements

1. Map the implementation: app entry point, routes, schemas, OpenAI client/provider, prompts, curriculum/catalog, configuration, dependencies, tests, and run instructions. Identify any SQLite/database/persistence code. The approved master prompt requires a stateless service that returns onboarding and roadmap data without storing user answers or roadmaps; SQLite persistence would be a scope mismatch unless the owner has since explicitly changed that requirement.
2. Compare actual behavior against the master prompt, not just the implementation summary. Prioritize correctness, user privacy, API key handling, predictable model output, route usability by a future React Native client, and roadmap quality.
3. Inspect the complete request-to-response path. Verify that follow-up rounds are capped server-side at two and questions at three per round; early completion works; repeated questions are avoided; user edits to the confirmed summary are respected; and the client supplies enough state on every stateless request.
4. Verify roadmap invariants in code and tests: exactly ten weeks, seven daily activities per week, ten minutes each, personalization based on goals/situations/struggles/constraints/preferences, approximately eight and a half weeks of focused work followed by one and a half weeks of broader skills, and only approved catalog activity types. Confirm the response does not claim measured progress or mastery.
5. Review the seed catalog and any internet research. Check that sources are credible, traceable, and accurately represented; distinguish sourced guidance from design choices; ensure course text is not copied. Report weak or unsupported claims and fix the source register/content where in scope.
6. Review safe handling: OpenAI credentials come only from `OPENAI_API_KEY` in the server environment; never print, log, return, commit, or expose secret values. Do not dump the environment. You may report whether a required variable is set, never its value. Do not send direct identifiers, raw audio, images, or video. Confirm full onboarding payloads are not logged or persisted.
7. Check failure handling for missing credentials, invalid credentials when safely testable, timeouts, rate limits, provider outage, malformed/invalid structured output, and exhausted bounded retries. Error responses must be useful without exposing secrets, prompts containing private answers, stack traces, or provider internals.
8. Check security and API quality: input bounds and validation, response schemas, CORS only if justified by the planned client, docs examples, no unsafe arbitrary model-generated activity types, no prompt injection from free text that can override system constraints, and no accidental database or file writes.
9. Verify dependencies and setup instructions are reproducible and consistent with the repository. Do not modify unrelated project decisions or build React Native screens, audio analysis, camera analysis, auth, or persistence.

## Testing protocol

- Start with inspection and the existing test suite. Use the project's documented environment and commands; do not install packages globally or alter lockfiles casually.
- Run deterministic tests with a mocked OpenAI provider. Tests must not require a real API key or make billable external calls.
- Include or strengthen tests for the full flow, schema validation, maximum rounds/questions, early stop, changed/edited profile, roadmap count and duration invariants, catalog allowlisting, statelessness, malformed model output, provider timeout/rate-limit failures, missing key, and privacy-safe errors/logging.
- Demonstrate that the API works when `OPENAI_API_KEY` is absent for non-provider routes and returns the documented safe error for provider-backed routes. Do not invent credentials.
- If a key is securely configured, an optional live smoke test may run only after checking its presence without printing its value. Avoid unnecessary calls and cost. If no key is present, explicitly mark live-provider testing as unrun while still completing mock-based tests.
- Use temporary test state and verify that no database, user profile, roadmap, or uploaded media is left behind. Do not delete pre-existing user data.
- Preserve exit statuses and report exact commands and actual outcomes. A passing suite does not prove curriculum quality or API access unless those were exercised.

## Fixing and reporting

Fix confirmed defects in scope, keeping changes small and aligned with the master prompt. Add tests for corrected behavior. Do not silently make high-level product decisions; list unresolved decisions separately. If a finding requires a product choice or missing credential, finish all independent checks and state precisely what is blocked.

At the end, report:

- Files and behavior actually found, including current branch and commit.
- Findings ranked by severity, with paths and concise evidence; clearly distinguish confirmed defects from risks or untested assumptions.
- Fixes made and why.
- Commands run and pass/fail/unrun outcomes.
- Whether mock API behavior passed and whether a live OpenAI request was run. Never include secret values.
- Remaining gaps, especially privacy/age-policy review before use with real users.

Do not claim the implementation is complete or production-ready if required behavior remains unverified.

# Backend context

Backend services, speech and movement integrations, personalization, and data storage. No architecture or provider selection has been finalized in these notes.

Read the repository-root AGENTS.md first. The team retains high-level decisions. Follow `../project/md/coding_rules.md` when coding, and consult `../project/md/project_status.md` for unresolved choices.

## Local directory

| Path | Purpose |
| --- | --- |
| `../../backend/README.md` | Backend startup and current API endpoints. |
| `md/` | Future topic notes; update existing notes before creating new ones. Currently empty. |
| `AI/master-implementation-prompt.md` | Historical implementation specification; later onboarding decisions supersede conflicting details. |
| `AI/audio-analysis.md` | Audio prototype, upstream model and dataset sources, CPU validation, and Kaggle research workflow. |
| `AI/Sherria Codex pickup.md` | Current project handoff, model/data access, verified results, setup, and next steps. Read this first when resuming model work. |
| `AI/onboarding-roadmap-plan.md` | Current adaptive onboarding and roadmap direction; supersedes the master prompt's 70-detailed-activities requirement. |
| `AI/second-review-and-fix-prompt.md` | Follow-up instructions for independently auditing, testing, and fixing the prototype against the master specification. |
| `skills/` | Approved reusable skills for this area; currently empty. |
| `AGENTS.md`, `CLAUDE.md` | Identical local instructions and directory index. |

## How we work

- Be honest, neutral, and slightly upbeat. Verify factual claims against project evidence or relevant sources; distinguish facts, proposals, and uncertainty. Say when something cannot be verified.
- Plan before executing. Investigate and explain a proportional plan for substantial work; keep simple work simple.
- The students own the ideas, goals, priorities, and high-level decisions. Agents implement the team's direction and may make routine implementation choices within the agreed scope. Ask before consequential changes or when the decision boundary is unclear. An explicit green light applies within its stated scope.
- Ask when essential information is missing rather than inventing details. Continue independent work that does not depend on the answer.
- Explain technical topics simply first, then add depth as needed. For substantial implementations, explain what changed, why, tradeoffs, and validation in enough detail for the students to understand and explain the work themselves.
- Work iteratively: make a small change, run meaningful checks, gather feedback when needed, refine, and repeat. Examine results and opportunities to improve rather than relying on one final test. Match test scope to risk and functionality.

## Maintaining context

- Keep shared preferences concise; keep project research, decisions, progress, and workflows in the appropriate project notes.
- After meaningful progress or a decision, update the relevant existing Markdown file. Create a descriptively named file only when no existing topic fits. More initial setup files are expected; avoid fragmenting established topics later.
- New folders and notes are allowed when useful. Update the relevant directory index when adding, moving, or removing context files.
- Flag stale, conflicting, or long-unreviewed information and clarify material conflicts. Record decision status and sources; do not silently convert a proposal into a decision.
- Tell the user whenever persistent information is recorded or updated, identify its location, and explain the reason.
- Never store credentials, bank details, or unnecessary sensitive personal information. Keep temporary task notes outside these durable files.
- Keep coding and research standards in separate project Markdown files and reference them from the relevant AGENTS.md. Do not invent project-specific workflows before they are established. Add email/calendar workflows only when defined and relevant.
- If a repeated process could usefully become an automated skill, ask whether the user wants that skill. After approval, build and verify it, then save descriptive Markdown instructions in the relevant area's skills/ folder. Do not create speculative skills or treat a note about automation as approval.
- Every AGENTS.md and CLAUDE.md pair in this repository must remain byte-for-byte identical. Whenever one changes, update its counterpart in the same change and check equality. CLAUDE.md is the intended name; references to cloud.md in the original request refer to this file.

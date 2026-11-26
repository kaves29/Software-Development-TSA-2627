# Speakly: team and agent guide

## Team and project

We are a four-person team of second-year high-school students in Buford, Georgia, competing in TSA Software Development with the goal of reaching nationals. The students lead the project; coding agents help implement and explain their work.

Speakly is the working title for a communication-practice app with goal-based exercises, speech feedback, progress tracking, and optional movement feedback. The repository contains project planning and an initial audio analysis prototype. Check the project status before describing features as implemented.

## Start here

1. Read this guide and `agent-context/AGENTS.md` (identical to this guide).
2. Read `agent-context/project/md/project_status.md` for current state, proposals, and unresolved decisions.
3. Read the relevant area's guide and notes before working there.
4. Follow `agent-context/project/md/coding_rules.md` for code changes and `agent-context/project/md/competition_info.md` for competition constraints.

## Repository directory

| Path | Purpose |
| --- | --- |
| `README.md` | Public overview of the planned app, proposed features, and roadmap. |
| `AGENTS.md`, `CLAUDE.md` | Identical repository-level instructions and navigation. |
| `agent-context/AGENTS.md`, `agent-context/CLAUDE.md` | Identical main context guides, kept synchronized with the root pair. |
| `agent-context/frontend/` | Frontend context: design, interface, and implementation decisions as established. Its `md/` folder holds notes; `skills/` holds approved reusable skills. |
| `agent-context/backend/` | Backend context: services, analysis, data, and integration decisions as established. Its `md/` folder holds notes; `skills/` holds approved reusable skills. |
| `agent-context/project/` | Shared project status, roles, coding rules, competition information, and supplied sources in `md/`; approved project-wide skills in `skills/`. |

Each area has an identical AGENTS.md/CLAUDE.md pair that indexes its local context. Empty folders use `.gitkeep` only so Git retains the structure. The audio analysis code is in `backend/speech_analysis/`. Other application source locations are determined as features are built.

The four main guides (root and agent-context pairs) must also stay identical. Work in the existing checkout; do not create a Git worktree unless the user requests it.

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

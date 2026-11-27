# Speakly Codex Pickup

## Read this first

This is a handoff for continuing the Speakly speech-analysis validation work. Start by reading this file, then obey the repository's `AGENTS.md` and inspect the current Git branch/status before editing anything. The present goal is **0.50 on every separately defined audio and video feature**. The eventual goal is 0.70. Do not call the goal achieved based on training loss, frame-level scores, a subset, or unverified predictions.

## Workspace locations

The expected repositories are siblings:

- `/workspace/Software-Development-TSA-2627` — Speakly product and analysis repository.
- `/workspace/Agent-Context` — shared instructions and skills. Inspect only its top-level `agent.md`/`AGENT.md` files, if present, and its `skills/` directory deeply. Do **not** read project folders, lab folders, research project content, or other project-specific directories in Agent-Context.

If paths differ, locate the repositories under the workspace without guessing from their names. Keep the Agent-Context reading restriction above.

## Required context reading

1. In Agent-Context, find and read the root-level `agent.md` or `AGENT.md` (case-insensitive filename) and the shared `skills/` folder. First inventory skill names and descriptions. Read relevant skills fully, including referenced instructions as appropriate. Prioritize experimental design, hypothesis generation, scientific critical thinking, literature review, research evidence qualification, statistical analysis/power, systematic debugging, and Ponytail/Superpowers if installed or available. Do not inspect Agent-Context projects.
2. In the Software-Development-TSA-2627 repository, read `AGENTS.md`, `README.md`, `GOALS.md`, `PROGRESS.md`, `BENCHMARKS.md`, and all project instructions. Then inventory every tracked file and read the repository source, tests, experiments, documentation, notebooks, and configuration extensively. Do not dump huge model/data files into context. For generated or third-party directories, inspect manifests, licenses, and interfaces without copying restricted data.
3. Inspect `git status`, recent history, branch, and remotes. Preserve user changes. Untracked `.agents/skills/ponytail` and `.agents/skills/systematic-debugging` may be workspace skill links. Do not commit them unless they are deliberate portable project files.
4. Inspect Kaggle attachment/logs by filename, timestamp and contents. The known attached `speakly-filler-continuous.log` is an older model run, not necessarily the failed `speakly-ami-adaptation` run. Do not claim it explains a failure unless the traceback matches. Search available attachments for the actual failed adaptation log and report if it is missing.

## User's goal and boundaries

- Build and validate the existing user onboarding analysis handoff for audio alone and audio plus optional video. It should produce human-readable observations suitable for a later roadmap stage. That later OpenAI/roadmap stage is out of scope.
- First reach **at least 0.50 on every feature**. The next target is 0.70. This is per-feature, not an average that hides failures.
- The user has asked for substantial iterative experiments, including Kaggle GPU runs where useful. A past Kaggle run is authorized, but this does not mean a run has started or succeeded.
- Use complete, realistic recordings and speaker-disjoint splits. Define metrics and tolerances before testing. Keep held-out evaluation labels out of tuning. Count abstentions/missing predictions consistently and report coverage, precision, recall, F1 or appropriate continuous-feature error, false alarms, uncertainty, split, and sample size.
- Never fabricate a score, describe a CPU rescore as a new training run, or say “0.50 achieved” from in-sample or oracle-transcript results.
- Keep multimodal optimization deferred until audio and video are validated separately. Do not proceed to website, live camera/microphone, OpenAI API, personalized roadmap, or push to the user's main repository unless separately authorized. Local commits of complete verified milestones are okay. The user has explicitly asked that they personally run the Kaggle notebook; do not start Kaggle execution on their behalf.
- Protect tokens and recordings. Never request or paste a raw Kaggle key in chat. Do not commit credentials, private audio/video, local caches, checkpoints, or generated predictions.

## Current known state

The historical research notes and precise results are in `BENCHMARKS.md` and `PROGRESS.md`. Read those sources rather than relying on this summary. Key points:

- The current feature inventory does not yet contain 15 independently validated audio and 15 independently validated video features. Many emitted fields lack suitable independent references.
- Recent corrected acoustic filler thresholding plus agreement scored about 0.489 pooled typed event F1 across eight previously analyzed complete AMI recordings. This is exploratory and close to, but below, 0.50.
- Verbatim ASR plus an acoustic corroboration rule scored 0.333 pooled repetition F1 on two complete recordings; baseline was 0.216. It remains below target.
- The best reported repeated-gesture classifier is still below 0.30 on presegmented development clips. No full-recording repeated-gesture validation has passed.
- A local ten-speaker adaptation was started from the uploaded continuous filler head, using 120 windows per each of ten training recordings and two development recordings. Its log is `/workspace/scratch/speakly-ten-track-cpu.log`, and output directory is `/workspace/scratch/speakly-ten-track-cpu`. The last confirmed log showed five epochs of training loss only; inspect for `metrics.json` before claiming any evaluation result. If it is absent, diagnose whether the process is still running or failed, and finish/resume evaluation where possible.
- The importable Kaggle notebook is in the GitHub repository at `backend/speech_analysis_onboarding_model/kaggle/Speakly-AMI-Adaptation.ipynb`, on branch `kaggle-ami-notebook` as of the last upload. It is also staged locally at `/workspace/scratch/speakly-ami-kaggle-draft/ami-adaptation.ipynb`. Verify live remote state before sharing.
- Notebook design: private Kaggle kernel, GPU and Internet enabled, ten AMI training speakers, two disjoint complete development recordings, verifies pinned audio and annotation hashes plus the `filler-continuous-head.pt` input, trains an AMI-adapted head and compares original/adapted models at two fixed thresholds. Results are copied to `/kaggle/working/speakly-ami-results/metrics.json`. User must attach the existing model output as a Kaggle input and choose **Save Version → Save & Run All**.
- Most recent cloud environment status had zero Kaggle secrets/runtime variables. User said they added a key, but re-check the environment binding/status; the new environment may differ. Never print secret values. If no key is available in the cloud environment, do not run/upload via CLI. The user can run the notebook directly on Kaggle. They explicitly said the assistant should prepare/fix it, and the user will execute it.
- There was an earlier attempt to deliver the notebook by copying it to `/workspace/shared/downloads`, but that did not make it visible as a direct chat attachment. The notebook was then uploaded to a dedicated GitHub branch. Do not claim a chat download is attached unless the current interface confirms it.

## Immediate next steps

1. Re-read `GOALS.md`, recent `PROGRESS.md`, recent `BENCHMARKS.md`, repository instructions, shared Agent-Context skills, and current Git state.
2. Check whether `/workspace/scratch/speakly-ten-track-cpu/metrics.json` exists and inspect the paired original/adapted development metrics. Verify each metric directly from output and confirm the expected complete recording durations and split. If no report exists, inspect the run's process/exit/error log and complete the remaining authorized local evaluation.
3. Find the exact Kaggle failure log. If it is absent, state that plainly and do not invent a cause. Improve the notebook's preflight errors so it reports missing model input, GPU state, internet/download failures, and failing subprocess output clearly. Keep training parameters/splits fixed unless a development-only comparison justifies a change.
4. Inspect current Kaggle credentials status without revealing secret values. If available, update the existing private notebook on its dedicated branch **without running it**. If unavailable, keep the corrected `.ipynb` ready for the user and explain exactly where to import it and what input to attach.
5. Continue one focused experiment at a time. Prefer fresh learning or full-recording inference when the question requires it. Cache rescoring is useful only when clearly labeled. Use a new, held-out speaker for any promoted claim. Update `BENCHMARKS.md`, `PROGRESS.md`, and `GOALS.md` with the method, command, split, result, failures, and limitations.
6. Run only validation checks needed for changes, inspect diffs, and commit verified local work. Do not push the product branch. Uploading a revised Kaggle notebook is allowed by the user's request, but do not execute it.

## Communication expectations

Give concise updates during long work, at least every minute. Be candid when a result is exploratory, below target, or unscored. The next report should clearly state (a) whether the local adapted model produced evaluation metrics, (b) whether the actual Kaggle traceback was found and fixed, (c) the exact notebook branch/path/version for the user, and (d) which features remain below 0.50 or lack independent labels.

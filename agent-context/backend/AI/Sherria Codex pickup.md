# Sherria Codex pickup

**Updated:** 2026-11-27
**Purpose:** Let a new Codex session resume the Speakly AI/audio-model work with the evidence and limits clear. This is a navigation and status document; the linked project notes remain the detailed source of truth.

## Read these first

1. [`/AGENTS.md`](../../../AGENTS.md) — team rules, ownership, and repository navigation.
2. [`../AGENTS.md`](../AGENTS.md) — backend-specific context and the index of AI notes. `CLAUDE.md` in the same folders must stay byte-for-byte equal to its `AGENTS.md` partner.
3. [`../../project/md/project_status.md`](../../project/md/project_status.md) — current project state, confirmed decisions, and unresolved choices.
4. [`../../project/md/coding_rules.md`](../../project/md/coding_rules.md) — project coding and test conventions.
5. [`audio-analysis.md`](audio-analysis.md) — full model/data sources, experiment history, metrics, limitations, and Kaggle workflow. Read its current-status section before using the historical experiment log.
6. [`onboarding-roadmap-plan.md`](onboarding-roadmap-plan.md) — latest owner-approved onboarding questions and roadmap direction.
7. [`master-implementation-prompt.md`](master-implementation-prompt.md) — historical specification. Its old follow-up questions and 70-detailed-activities requirements were superseded by the onboarding plan.
8. [`second-review-and-fix-prompt.md`](second-review-and-fix-prompt.md) — previous audit instructions; use as history, not as a current feature specification.

The owner also asked agents to consult the separate [`kaves29/Agent-Context` repository](https://github.com/kaves29/Agent-Context), especially its [`AGENTS.md`](https://github.com/kaves29/Agent-Context/blob/main/AGENTS.md), for shared collaboration preferences and project routing. That repository currently describes other research projects; do not transfer their datasets, methods, personal details, or decisions into Speakly. Use only guidance that applies to this software project. The Speakly-specific guides in this repository take precedence for Speakly work.

## What the owner is working on

The owner is leading Speakly's AI/model work for a student software-development project. Their goal is to turn two or three short English onboarding samples, together with answers the user confirms, into useful evidence for a personalized ten-week speaking roadmap. The front-end work belongs to teammates. The owner's current focus is the server-side audio/video analysis and model research; model quality and honest validation matter more than claiming a large feature count.

The product direction is not to diagnose a user. The evaluator should report observable speech or movement evidence with quality limits. The roadmap generator can use supported evidence alongside the person's chosen goal. Avoid medical or psychological labels, accent judgments, or claims that a practice app treats a disorder. A number of output fields is not the same as a number of distinct, accurate capabilities.

The current GitHub `main` branch also contains a browser-based practice prototype, including presentation/interview practice and optional microphone recording. That work is documented in `project_status.md`; it is not yet connected to this AI analysis or roadmap API. The owner’s intended mobile app is a separate team implementation.

## Repository map

| Location | What is there |
| --- | --- |
| [`backend/speech_analysis/`](../../../backend/speech_analysis/) | Python CLI, audio and video measurements, multi-sample aggregation, model training/evaluation, and roadmap API. |
| [`backend/speech_analysis/tests/`](../../../backend/speech_analysis/tests/) | `unittest` suite for deterministic code paths and failure cases. |
| [`backend/speech_analysis/kaggle/`](../../../backend/speech_analysis/kaggle/) | Reproducible Kaggle notebook and private-kernel metadata generated from the checked-in training code. |
| [`backend/speech_analysis/roadmap.py`](../../../backend/speech_analysis/roadmap.py) | Stateless FastAPI `POST /api/roadmap/generate`; uses an OpenAI Responses API call when configured, or an injected mock provider in tests. |
| [`backend/speech_analysis/handoff.py`](../../../backend/speech_analysis/handoff.py) | Reduces confirmed profile and recording outputs to roadmap evidence. |
| [`backend/speech_analysis/session.py`](../../../backend/speech_analysis/session.py) | CLI for two or three recordings, preserving sample-level results and missing evidence. |
| [`agent-context/project/md/project_status.md`](../../project/md/project_status.md) | Overall project decisions and status. |

## Current implementation, in plain terms

### Audio

The analysis pipeline reuses speech decoding/transcription and timing, Silero VAD speech regions, and acoustic/transcript measurements. The experimental filler detector is a frame classifier: frozen `microsoft/wavlm-base-plus` representations feed a small three-class head (`other`, `um`, `uh`). The four-second checkpoint uses 20 ms frame labels and overlapping windows at inference. This is a small trained head over a large upstream encoder, not a newly trained LLM or a fully fine-tuned WavLM.

Latest AMI evidence and run status are in [audio-analysis.md](audio-analysis.md#latest-kaggle-review-2026-11-27). In brief: none of the five behaviors with labels meets the 0.50 target; 30 of 35 listed rows have missing references, not scores. AMI adaptation did not improve pooled filler F1. One audio-validation kernel has no captured cell outputs or metrics, and a separate adaptation attempt failed because Kaggle had no GPU attached. Check the dated audio note before proposing another training recipe.

Other reported values include speaking rate, pauses, changes in rate, pitch/energy variation, repetitions/revisions, and transcript organization/content observations. Some are direct measurements; others are heuristics marked `experimental`. Do not turn these into weakness labels without reference data and a defensible threshold. The repeat/repair head has poor evidence and is not a validated detector.

### Video

`video.py` contains optional MediaPipe landmark analysis, camera-motion estimation, and temporal rules for movement evidence such as gesture rate, torso/head/hand motion, pose coverage, and hand-to-face proximity/returns. It does not contain a trained video behavior classifier or a labeled speaking-video benchmark. Movement can be described as visible movement; it cannot establish nervousness. Treat video values as experimental and abstain when framing, tracking, or camera stability are inadequate.

### Roadmap and onboarding

`roadmap.py` is a stateless route that validates a confirmed goal/profile and two or three sample results, retains only supported observations for its model input, and asks the OpenAI Responses API for ten broad weeks and seven current-week activities from a fixed catalog. The code and mock-provider contract exist; a live API call has not been verified here because no OpenAI key is configured. Never put a key in this file, Git, Kaggle, a notebook, or chat; use a secure environment secret. The initial question flow and adaptive follow-up service are not a completed end-to-end mobile onboarding experience in this checkout.

The owner-approved product questions and roadmap cadence are in `onboarding-roadmap-plan.md`. The implementation still needs verification against that latest plan. The mobile client, account storage, real-user analysis flow, and live OpenAI integration are not validated here. The separate browser prototype has microphone capture/playback, but no AI analysis connection.

## Model, dataset, and notebook locations

### Trained filler checkpoint

- Private Kaggle notebook: [Speakly Filler Continuous](https://www.kaggle.com/code/shouryakaveti/speakly-filler-continuous).
- Latest Kaggle status checked **2026-11-25:** `COMPLETE`.
- Downloaded output: `filler-continuous-head.pt` (about 11.3 KB), Kaggle SHA-256 `68aee44b596e7a36c46f5c1aaa083b4dfb0c46aa1cd4540872cc211484f19ca4`.
- The output was retrieved during this session into temporary `/tmp` storage. That directory is not durable and is not the canonical copy; retrieve it from Kaggle when needed.
- The checkpoint contains the trained frame-classification head, not the WavLM backbone. The code downloads the pinned WavLM encoder revision `4c66d4806a428f2e922ccfa1a962776e232d487b` from Hugging Face at inference/training time.
- This checkpoint is research-only because it is derived from PodcastFillers. Do not commit or publish it to the public GitHub project unless the dataset terms are reviewed and the team confirms that redistribution is permitted.

### Training code and data

- Training/evaluation implementation: [`train_filler_frames.py`](../../../backend/speech_analysis/train_filler_frames.py), [`filler_frames.py`](../../../backend/speech_analysis/filler_frames.py), [`fillers.py`](../../../backend/speech_analysis/fillers.py), and [`kaggle_job.py`](../../../backend/speech_analysis/kaggle_job.py).
- Notebook checked into GitHub: [`speakly-filler-continuous.ipynb`](../../../backend/speech_analysis/kaggle/speakly-filler-continuous.ipynb). It embeds the project training code at generation time and sets internet/GPU metadata. The private kernel version can differ from this notebook; pull/compare before assuming they are identical.
- Dataset: [PodcastFillers on Zenodo](https://zenodo.org/records/7121457); [annotation terms](https://podcastfillers.github.io/license/). The dataset archive is roughly 6 GB, labels are candidate annotations rather than exhaustive ground truth, and the terms restrict use to noncommercial research. The data is not checked into GitHub and should not be mirrored there.
- The continuous Kaggle notebook retrieves the archive/labels, verifies expected checksums, selects train/validation recordings, and trains with two T4 GPUs. It needs working Kaggle internet access to fetch Zenodo/Hugging Face data and PyPI dependencies unless a complete offline bundle is attached.
- [DisfluencySpeech](https://huggingface.co/datasets/amaai-lab/DisfluencySpeech) is a research/development source for marked repair examples. It has a single-actor limitation; annotation gaps do not mean there were no disfluencies. No useful generalizing repetition/repair model was established. Do not treat it as comprehensive truth.
- Whisper, WavLM, Silero, and MediaPipe are upstream packages/models. Their weights are downloaded from official sources; do not copy multi-gigabyte caches into Git. Confirm each upstream license for the team's intended use.
- Raw audio, full public datasets, downloaded third-party weights, Kaggle credentials, and user recordings belong outside the source repository. Use official download instructions or private research storage, with checksums and license notes.

The separate [`Agent-Context`](https://github.com/kaves29/Agent-Context) repository is not the model/data store for Speakly. The current project checkout and private Kaggle notebook/output are the relevant locations.

## What the latest results mean

The full timeline and tables are in `audio-analysis.md`. Key findings:

| Result | What it establishes | What it does not establish |
| --- | --- | --- |
| Kaggle train completed three epochs on two T4s; frame validation filler mean F1 was 0.875 at epoch 3. | The training pipeline ran and learned to match labeled frames. | Event-level performance on user recordings or 85–90% accuracy. |
| Best four-second validation decoder reached 0.621 event midpoint/boundary F1 on two short annotated excerpts. | There is a measurable baseline on a small set. | Reliable generalization; annotations may miss real fillers. |
| On Claire Zorn's held-out 180-second excerpt, frozen decoder settings reached 0.762–0.824 event F1 depending on threshold/duration. | It detects some events in another recording. | A stable threshold: the one-second version scored 0.449 on a prior Pat Finn excerpt. Different settings/recordings make these noncomparable as a single final score. |
| Video synthetic tests pass for controlled camera movement and landmark tracking. | Code handles selected controlled conditions. | Real-world video behavior accuracy. |
| CPU test run here discovered 43 tests; 37 passed and 6 errored. | The available environment ran the dependency-light cases. | Full suite passing: errors came from missing `torch`, `pyarrow`, and OpenCV (`cv2`), and test dependencies need setup. |

**Current acceptance status:** the user's requested 80% interim performance has not been demonstrated across independent speakers/recordings. The 85–90% goal remains unmet and is not currently measurable for most output fields because labeled, representative data is missing. Never tell the owner that the evaluator is “ready for pilot” under those thresholds.

## Kaggle access and commands

In the managed Codex environment, `KAGGLE_API_TOKEN` was reported ready and the Kaggle CLI worked after setting a writable config directory. The actual credential was never printed or added to files. This is a Kaggle API token only; there is no configured Composio connector in the current tool list.

```bash
# Use a writable config location in this managed workspace.
export KAGGLE_CONFIG_DIR=/tmp/speakly-kaggle-config
mkdir -p "$KAGGLE_CONFIG_DIR"

# Check the private run and retrieve its generated output.
kaggle kernels status shouryakaveti/speakly-filler-continuous
kaggle kernels output shouryakaveti/speakly-filler-continuous -p /tmp/speakly-kaggle-output

# Generate a fresh notebook/metadata pair from the checked-in code.
PYTHONPATH=backend python backend/speech_analysis/kaggle_job.py \
  --continuous shouryakaveti /tmp/speakly-continuous-notebook

# Upload a reviewed notebook version to Kaggle (only after checking the diff/config).
kaggle kernels push -p backend/speech_analysis/kaggle
```

On a personal machine, install the official Kaggle CLI and create a Kaggle API token from Kaggle account settings. Store it using the CLI's secure local configuration method; do not paste the token into chat, a notebook, environment docs, or source control. Kaggle may require accepting the dataset's terms before downloads. Use the private Kaggle project because the data and model are research-only. Do not enable a training run repeatedly without the owner's intent; report its status instead of polling on a schedule.

Composio is not needed for the current Kaggle workflow and is not connected here. If it becomes necessary, locate and review its official setup and permissions with the owner before granting access. Never infer that an integration is configured simply because it was mentioned.

## Resume workflow and next steps

1. Read the project guides above and inspect `git status`; preserve any current edits. Confirm you are in `kaves29/Software-Development-TSA-2627` and check the `main` branch before making new changes.
2. Read the latest Kaggle log/output and compare with `audio-analysis.md`. Reproduce the SHA-256 before using a downloaded checkpoint. Do not reuse the test set to tune thresholds.
3. Set up the project dependencies from the relevant `requirements*.txt` in an isolated environment. Run the tests with `PYTHONPATH=backend`; missing Torch, PyArrow, and OpenCV currently prevent a complete suite in this environment.
4. Prioritize a small, speaker-disjoint, exhaustively reviewed set of continuous recordings. Candidate annotation lists are not exhaustive; never turn an unmarked interval into a hard negative without review. Preserve separate validation and untouched test data. The current AMI development tracks have already been used for model and threshold investigation; reserve new speakers for future validation.
5. Improve event-level filler evaluation with frozen validation thresholds, more episodes and error review before another expensive training run. Report event precision/recall/F1, false alarms per minute, timing error, label coverage, and recording quality separately.
6. Do not claim 15 audio or 15 video weaknesses based on field count. For each proposed behavior, record its operational definition, evidence source, labels, coverage, metric, result, and limitation. Keep unsupported behaviors experimental or unavailable.
7. Video needs labeled speaking samples before a trained classifier or an accuracy claim. Movement is observable evidence; it cannot identify nervousness.
8. Verify roadmap inputs are supported, privacy-minimized, and profile-confirmed. The OpenAI key is a later secure configuration step, not proof the evaluators are already accurate.
9. After each meaningful change or experiment, update the existing `audio-analysis.md` (and `project_status.md` when overall state changes) with date, code/notebook revision, dataset/split, run settings, checksums, metrics, and limitations. Add a new Markdown file only for a distinct durable topic, update the directory index, and keep paired `AGENTS.md`/`CLAUDE.md` files identical. Tell the owner which notes changed.
10. Explain results in simple language and give the owner the source paths so they can understand and present the work. Do not publish, deploy, or claim a performance milestone based only on synthetic checks or one short podcast excerpt.

## GitHub boundary

The public repository is for source, tests, small reproducible metadata, notebooks, and documentation. It is **not** the place for PodcastFillers audio/labels, user recordings, upstream model caches, API credentials, or the current PodcastFillers-derived checkpoint. Those are large and/or subject to research-only terms. The code plus versioned data source, exact split, checksums, Kaggle kernel URL, and checkpoint hash provide a safer reproducible trail. If a dataset or model license changes, review it before adding the artifact.

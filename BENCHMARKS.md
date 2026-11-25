# Speakly analysis benchmarks

Historical scores below come from the research notes and are not fresh reruns. The acceptance protocol is in [GOALS.md](GOALS.md).

| Area | Existing evidence | Acceptance status |
| --- | --- | --- |
| Continuous fillers | Four-second model validation event F1 0.621 on two annotated excerpts. Frozen settings gave 0.762–0.824 midpoint F1 on one 180-second held-out excerpt. Candidate annotations may omit fillers. | No pass |
| Repetitions and repairs | Transcript heuristic development checks on one acted speaker. Experimental clip-level model missed all 73 labeled repetitions in one held-out set. | No pass |
| Other audio | Existing unit and smoke checks cover calculation and error handling. | Independent per-feature scores unavailable |
| Video | Controlled landmark and camera movement tests. No labeled realistic speaking-video benchmark in the checkout. | Independent per-feature scores unavailable |
| Multimodal | Session aggregation exists. | No fusion benchmark |

The current event evaluator can score timestamped predictions on a labeled recording and pool event counts across full recordings. It needs feature-specific continuous scoring, coverage reporting, and a split manifest before it can support all acceptance decisions.

## Reproduced software baseline

61 existing tests passed with CPU Torch 2.15.0, OpenCV headless 5.1.0.95, and the repository versions of PyArrow, SoundFile, librosa and Transformers. Run from the repository root with `PYTHONPATH=backend python -m unittest discover -s backend/speech_analysis_onboarding_model/tests`. This suite includes synthetic tests and local fixtures. No feature has a new held-out performance score from this run.

## AMI annotation inventory

Downloaded the CC BY 4.0 [AMI manual annotations v1.6.2](https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip) and verified SHA-256 `b56e5babb2496b8795deeeda7e71178d7fbc9963f94276cf2a3f4b56ebbc9f9d`. Counting the meeting identifier from each XML basename found 171 meetings with word files, 40 with disfluency files, 46 with head gesture files, and 17 with hand gesture files. Only four meeting identifiers appear in all four layers. These counts do not verify participant-level overlap, media availability, exhaustive labeling, or speaker independence. Meeting speech can support selected development benchmarks, with a separate onboarding-like benchmark needed to measure transfer.

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

### Full-recording development case

AMI ES2008a participant A maps to Headset-0 and Closeup4. The full headset file is 1043.360 s (SHA-256 `9038704a0c2380b3abed17af3927e110a3783d3e8a0a7743af86275552f5588a`) and the full video is 1036.040 s (SHA-256 `6c70adf847e527b47ffeeed10abf197a8429dfe4e4a50d13c62c637078b29305`). The corpus documents synchronization procedures for TNO. Verify start offset, drift, and the uncovered tail for this Edinburgh pair before comparing cross-modal events.

The annotation intersection covers eight distinct AMI speaker IDs across two recurring groups. Keep both meetings in each series together. ES2008a is development material because its labels have been examined. Its participant A word annotation contains 54 `um` and four `uh` events.

```sh
PYTHONPATH=backend python -m speech_analysis_onboarding_model ES2008a.A.wav \
  --model tiny.en --max-seconds 1200 > ES2008a.A.json
PYTHONPATH=backend python -m speech_analysis_onboarding_model.evaluate_ami \
  ami_public_manual_1.6.2.zip ES2008a.A.json
```

```sh
PYTHONPATH=backend python -m speech_analysis_onboarding_model.video ES2008a.A.avi \
  --pose-model pose_landmarker_lite.task --hand-model hand_landmarker.task \
  --face-model face_landmarker.task --max-seconds 1200 > ES2008a.A.video.json
```

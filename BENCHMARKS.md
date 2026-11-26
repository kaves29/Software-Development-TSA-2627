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

The AMI head and hand labels encode communicative events. For example, ES2008a.A has 49 concord signals, 39 emphasis signals, and nine labeled communicative hand intervals. These labels cannot serve as reference tracks for fingertip-to-face proximity, exact landmark positions, or the full set of pose measurements. [AVA Active Speaker](https://research.google.com/ava/download.html#ava-active-speaker-download-v10) is a candidate external check for visible speech attribution. It does not cover the remaining fusion features or the onboarding domain.

The full headset run with Whisper tiny.en and Silero VAD, without a filler checkpoint, took 252.729 s on CPU and returned no analysis errors. At the 250 ms two-boundary tolerance, it matched one of 58 references with four predictions: precision 0.250, recall 0.0172, F1 0.0323, and 0.173 false alarms per minute. The mean boundary error was 0.110 s on the single match. This is a development result from one speaker and is far below acceptance.

A separate Silero pass found that all 58 annotated filler intervals overlap at least one predicted speech interval. Entirely missed speech regions therefore do not explain the poor filler recall on this recording. This overlap check does not rule out speech boundary errors or timing errors in recognized words.

A local Whisper comparison used a verbatim prompt mentioning filled pauses and disabled the VAD word filter. It matched two of 58 references with eight predictions (precision 0.250, recall 0.0345, F1 0.0606). Both settings changed together, so the run does not isolate either effect. This is well below acceptance and does not justify changing the default transcript path.

The full close-up video run processed 5,180 frames at 5 fps with MediaPipe pose, face and hand models. Pose was detected in 4,908 frames (94.75%), face in 3,306 (63.82%), and at least one hand in 598 (11.54%). Fingertip-to-face proximity had 529 usable frames (10.21%). Camera motion was classified as low translation with 4,846 tracked transitions. These are output coverage statistics, not reference-based accuracy scores.

The verified uploaded WavLM frame checkpoint scored **0.3396 event F1** on the full 1,043.36 s development recording with the historical decoder (.80 threshold, 12 consecutive frames). It matched 18 of 58 references with 48 predictions. A development-only sweep over thresholds, minimum consecutive frames, and onset/continuation hysteresis found 0.4252 F1 at .60 and 12 frames (27 matches, 69 predictions). Matching at 500 ms and 1 s yielded 39 and 48 matches respectively, which shows sensitivity to timestamp error. The acceptance tolerance remains 250 ms. Ignoring the filler class at 250 ms gives only 29 matches, so label confusion by itself explains little of the gap.

A development-only grid over fixed boundary shifts and padding selected .60/12 with a 100 ms later center and 60 ms outward expansion at both endpoints (equivalent to start +40 ms and end +160 ms, clipped to recording duration). This setting yielded 33 matches and 0.5197 F1 at the original tolerance. Freeze it alongside the historical .80/12 comparison before scoring TS3005a.A. This is candidate calibration from one recording and does not change production defaults.

At the development-selected .60/12 setting, after the 100 ms center shift, 50 of 69 predicted midpoints fell inside an annotated filler, 16 inside other annotated words, and three outside annotated words. These are prediction counts and may include multiple hits on one reference. The 33 strict event matches show that many promising candidates still have inaccurate boundaries. A separate fixed-duration grid peaked at 0.4554 F1 on the same recording, below variable-length boundary correction.

### Frozen transfer check

TS3005a.A is a different AMI speaker group from ES2008a.A. Its full 1,318.848 s Headset-0 stream has SHA-256 `7ca6fe56d9a8b2294ff69a13466ebce1c408434f2f457a245eec792b5fa266f9` and 113 labeled fillers. Both decoders were fixed before these labels were scored.

| Decoder | Matches / predictions | Precision | Recall | Event F1 | Unmatched predictions/min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical .80/12 | 52 / 104 | 0.500 | 0.460 | 0.479 | 2.366 |
| Development .60/12 plus boundary correction | 58 / 152 | 0.382 | 0.513 | 0.438 | 4.276 |

The corrected decoder recovered six additional matches but added 48 predictions, so the improvement on ES2008a.A did not transfer. Keep the historical decoder as baseline. Both AMI recordings are now evaluated and must not be reused as final untouched test material for a model developed in response to these results. A subsequent training experiment should test whether continuous in-domain speaker-disjoint negatives and an explicit boundary prediction objective improve this baseline. Evaluate that experiment on fresh speakers and preserve the two-boundary metric.

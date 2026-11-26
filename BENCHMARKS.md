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

### AMI split audit for the next training experiment

Use the archive's official train/development/unseen meeting assignments. `ami_split` verifies global speaker identities across all assigned meetings, including speakers without word files, and rejects prior evaluation speakers in test. It yields 392 train tracks from 100 speakers, 80 development tracks from 20 speakers, and 80 test tracks from 20 speakers. No global speaker IDs cross the three partitions. ES2008a and TS3005a are official training meetings. Their existing scores are transfer diagnostics for the PodcastFillers checkpoint. They cannot measure generalization of an AMI-trained model.

`ami_training` reads only train/development word files. It exports 19,200 labeled fillers and 453,871 other word spans for training, plus 4,190 labeled fillers and 94,969 other word spans for development. Gaps without a word reference remain unlabeled. Use the official test set once the candidate, event decoder, and comparison are frozen. The manifests verify identity and split annotations; full media availability and annotation completeness must be checked per track.

```sh
PYTHONPATH=backend python -m speech_analysis_onboarding_model.ami_split ami_public_manual_1.6.2.zip > splits.json
PYTHONPATH=backend python -m speech_analysis_onboarding_model.ami_training ami_public_manual_1.6.2.zip training-words.csv
```

For the next comparison, hold the WavLM encoder and recording-level scorer fixed. Train a frame head on AMI training meetings with both filler classes and annotated ordinary speech, and compare it with the original checkpoint. Select checkpoints and decoders on official development meetings by pooled 250 ms event F1. Report per-speaker and per-class results, false alarms per minute, and uncertainty by resampling speakers. Freeze both models and their decoders before opening official test labels. An explicitly requested final full-system test will still need suitable labels and representative capture for video and multimodal features.

A CPU smoke run used the first 12 grid windows per split and one epoch, beginning from a fresh head. Training windows lacked `uh` and development windows lacked `um`. The training and development frame F1 values were 0.036 and 0.011. This verifies the data and training path and is too small and class-incomplete to evaluate improvement. Use a 2-second grid hop for the larger continuous-recording pilot and verify both labels are present in each exported subset before training.

### Official development recording IS1008a.D

We ran the verified PodcastFillers head on the full 943.787 s development headset (SHA-256 `a60e45356e8324231ba259bc63046d68aefc17b4a063a6a497736e7cb525642a`). The historical decoder matched 6 of 16 references with 40 predictions (precision 0.150, recall 0.375, F1 0.2143). The fixed boundary correction matched 9 with 80 predictions (F1 0.1875). A regularized boundary regressor fitted on 127 timestamp pairs from the two official training recordings also matched 9 with 80 predictions (F1 0.1875). Neither correction replaces the baseline.

Eighteen of the 40 historical predictions had a midpoint within 250 ms of another participant's annotated filler and no target-speaker filler. This is evidence of possible headset bleed, with competing speech attribution worth testing. It does not establish that all 18 events are crosstalk or that a single-channel speaking sample would behave the same way.

A development-only crosstalk diagnostic compared target Headset-3 against the one available competing stream, Headset-1. Keeping events at least 6 dB stronger on the target stream retained all six strict matches and removed 29 unmatched predictions: precision 0.545, recall 0.375, F1 0.4444. The 0 and 3 dB trials gave F1 0.2308 and 0.3243. The other two headset downloads returned HTTP 503 after retries, so the all-channel comparison remains unrun. This is a one-recording diagnostic that requires an extra synchronized audio channel; it does not support deploying this threshold for single-mic onboarding. Recall was unchanged, so speaker attribution alone is insufficient.

A second competing headset (Headset-2) became available for IS1008a.D. Comparing target RMS against the larger of the two available competing-channel RMS values gave 0.4615 development F1 at both 3 dB and 6 dB, with 6 of 16 references matched and 10 predictions. The 0 dB result was 0.375. These are still one-recording, extra-channel diagnostics. A third competing headset is needed for the complete comparison. Recall stayed 0.375.

### Warm-start adaptation experiment

The next pilot froze the uploaded WavLM encoder and fine-tuned its existing linear head on 120 four-second windows, sampled evenly from ES2008a.A and TS3005a.A with seed 42 and a two-second hop. Sampled frames included both filler classes. The objective used inverse square-root class weights on annotated frames only, five passes through the cached features, and AdamW at 0.0003. Full-recording scoring uses the fixed 0.60 and 0.80 thresholds, 12 consecutive frames, and the unchanged 250 ms two-boundary scorer. Additional training recordings could not be retrieved from the AMI mirror (HTTP 503). The small sample is a development experiment rather than a generalization claim.

To reproduce with the same three complete WAV files named by recording ID and the uploaded checkpoint:

```sh
PYTHONPATH=backend python -m speech_analysis_onboarding_model.adapt_ami_filler \
  ami_public_manual_1.6.2.zip recordings filler-continuous-head.pt adaptation-output \
  --train ES2008a.A --train TS3005a.A --development IS1008a.D
```

The runner writes input digests and sampled window offsets. It rejects official test recordings for either role. It can use CUDA when available; the local pilot ran on CPU.

The warm-start pilot finished the complete IS1008a.D development comparison:

| Head | Decoder threshold | Matches / predictions | Precision | Recall | Event F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 0.60 | 8 / 80 | 0.100 | 0.500 | 0.167 |
| Original | 0.80 | 6 / 40 | 0.150 | 0.375 | 0.214 |
| Adapted | 0.60 | 5 / 38 | 0.132 | 0.312 | 0.185 |
| Adapted | 0.80 | 3 / 14 | 0.214 | 0.188 | 0.200 |

Adaptation suppressed predictions, including correct detections. The training loss improvement did not produce a better maximum among the two predeclared thresholds on this development track. Do not promote the adapted head on this result.

The same two-speaker head was compared on full development track TS3004a.A (1,345.323 s, SHA-256 `bde78c71e744b535f860964160857b646c3052c1286a4fb2c015fccf8991dcf0`) using the same encoder features for both heads. Original F1 was 0.3605 at .60 and 0.2609 at .80. Adapted F1 was 0.3248 at .60 and 0.2680 at .80. Pooling the two development tracks gives original F1 0.2910 (.60) and 0.2456 (.80), versus adapted F1 0.2807 (.60) and 0.2520 (.80). At .60, adaptation reduced unmatched predictions from 150 to 68 but also reduced correct matches from 39 to 24 across 79 references. Do not promote this head.

The mirror later supplied three additional annotated training tracks (ES2005a.A, ES2006a.A and TS3009a.A). The follow-up pilot samples up to 60 windows per track from five distinct training speakers with the original checkpoint, seed, loss and scoring settings kept fixed. Source paths, hashes and sampled offsets are recorded in the local run manifest. The official AMI test set remains sealed.

The five-speaker run used 268 windows (60 per track except 28 available for ES2005a.A) and 40,123 annotated frames. On full development track IS1008a.D, adapted F1 was 0.200 at .60 and 0.167 at .80, compared with 0.167 and 0.214 for the original head. Its best fixed score did not beat the baseline. This is the second small-head pilot that reduced false alarms but failed to improve the best development F1. Do not promote either adapted head. The prepared private notebook tests a larger ten-speaker training budget and evaluates both complete development tracks. It pins all corpus audio, archive and starting checkpoint hashes. Its input setup passed a dry run against the complete local media; the CUDA job has not been submitted. Keep the released test set out of this run.

### Released-model comparison

Zhu et al.'s [neural semi-CRF paper](https://www.hajim.rochester.edu/ece/projects/air/publications/Zhu23FillerWord_pdf.pdf) reports 0.769 event F1 on PodcastFillers for its S4/semi-CRF acoustic detector and releases [research code](https://github.com/gzhu06/Filler-semi-CRF). Its data and scoring differ from our full-length, typed AMI benchmark. The paper identifies short fillers, vowel-like ordinary words, and boundary errors as recurring failure modes. [CrisperWhisper](https://www.isca-archive.org/interspeech_2024/zusag24_interspeech.pdf) instead fine-tunes ASR for verbatim output and word alignment. Its filler-localization experiment used windows centered on known fillers, so its published scores do not establish precision over entire recordings. Its [released inference implementation](https://github.com/nyrahealth/CrisperWhisper) can be evaluated directly under the existing scorer.

Ran the [Desert Ant Uhm SDK](https://huggingface.co/desert-ant-labs/uhm), Node native version 6.0.0, at balanced bias on complete development recordings. Linux SDK detections are untyped. Under the same 250 ms boundary tolerance but ignoring the filler class, it matched 6/16 on IS1008a.D (12 predictions, F1 0.429) and 29/63 on TS3004a.A (46 predictions, F1 0.532). Pooled F1 was 0.511 (35 matches, 58 predictions, 79 references). The vendor reports using AMI audio during training, with overlap against these exact development tracks unverified. Treat this comparison as exploratory. The [license](https://license.desertant.com/1.2) requires using the published SDK. A direct ONNX attempt was stopped before producing metrics after confirming that restriction.

On IS1008a.D, labeling each SDK span by the sum of cached WavLM probabilities within the span preserved all six matches and gave 0.429 typed F1 (precision 0.500, recall 0.375), against 0.214 for the original decoder. This one-recording hybrid is promising for precision. It does not establish a 0.70 score or independent generalization.

CrisperWhisper Small 2.0 (package 2.1.0, upstream model revision `bcaecf0a584a1f600d8897fe6032b9e2e56429a7`, CPU int8) was run with word timestamps on complete development file IS1008a.D. The first recording produced 159 literal `um`/`uh` candidates and matched eight of 16 references at the original 250 ms two-boundary tolerance. Precision was 0.050, recall 0.500 and F1 0.0914. Verbatim transcription alone did not solve excessive detections on this meeting channel. This is a different model and evaluation regime from the Interspeech paper. A second development recording was launched with unchanged settings.

A simple union of SDK spans and non-overlapping original WavLM detections on IS1008a.D recovered 9 of 16 references, but produced 46 predictions (precision 0.196, F1 0.290). This is worse than the 0.429 typed SDK-span hybrid, so naive union is not a candidate. A future combination needs stronger evidence for missed events and target-speaker attribution; merely adding predictions raises false alarms.

The second full CrisperWhisper Small development run on TS3004a.A matched 39 of 63 references from 158 predictions, for 0.353 typed event F1. Pooled over the two complete recordings, it matched 47 of 79 references from 317 predictions (precision 0.148, recall 0.595, F1 0.237). It gains recall but falls below the WavLM pooled baseline of 0.291. The CrisperWhisper and SDK probes suggest complementary behavior, but an evidence-driven combination needs to rule out background speakers and preserve more of the true detections before a frozen test. No official test audio or labels were used in these comparisons.

### Hybrid detector follow-up

Ran Uhm SDK 6.0.0 in recall mode on the same two complete development recordings and assigned each returned span an um/uh type using the uploaded WavLM head's summed frame probabilities. At the unchanged 250 ms two-boundary tolerance, balanced mode produced 35 matches out of 58 predictions and 79 references (precision 0.603, recall 0.443, F1 0.511). Recall mode produced 39 matches out of 74 predictions (precision 0.527, recall 0.494, F1 0.510). The first development recording improved from 0.429 to 0.457 while the second declined from 0.532 to 0.525. These are development results, and the Uhm model card reports AMI training with exact track overlap unverified. Do not claim independent generalization or promote either mode. The official test split remains unopened.

### Cross-speaker agreement filter

Tested a development-only filter that keeps recall-mode SDK events when the WavLM mean probability for its selected filler class exceeds a threshold. Thresholds 0.0 through 0.8 in steps of 0.1 were selected on one recording and applied to the other. Training on IS1008a.D selected 0.5 and scored 0.526 on TS3004a.A. Training on TS3004a.A selected 0.4 and scored 0.457 on IS1008a.D. Ties chose the highest threshold. The unfiltered recall scores were 0.525 and 0.457 respectively. This did not materially improve transfer. Both recordings have been used for model selection and cannot serve as final held-out tests. Uhm's training overlap with AMI remains unverified.

### Switchboard-trained acoustic model and agreement probe

The research repository [Disfluency Detection From Audio](https://github.com/amritkromana/disfluency_detection_from_audio) provides a WavLM-based five-label acoustic checkpoint. The downloaded checkpoint's SHA-256 is `8724aaac4da9ae4d6e04f55dc394650a2517fbf529f5f4cd00b1353c74547036`. Its repository has no explicit license and the upstream training/test speaker provenance relative to AMI has not been established, so this is a local exploratory comparison. The implementation was run in overlapping 12-second windows, rather than the repository's whole-recording demo, on the two existing AMI development tracks. Frame label zero is filled pause. Contiguous positives of at least 120 ms were labeled um/uh using the prior WavLM head and scored at 250 ms on both boundaries.

At the 0.5 threshold, IS1008a.D had 12 matches, 65 predictions and 16 references (precision 0.185, recall 0.750, F1 0.296). TS3004a.A had 36 matches, 79 predictions and 63 references (precision 0.456, recall 0.571, F1 0.507). The first result recovered more true fillers than the previous hybrid while producing many false positives.

A preliminary agreement filter retained a new-model event only if its midpoint was within a selected time window of an Uhm recall event. The window was selected from 0.1, 0.25, 0.5, and 1 second on one recording and evaluated on the other. Choosing IS1008a.D produced a 0.1-second window and F1 0.524 on TS3004a.A (27 matches, 40 predictions, 63 references). Choosing TS3004a.A produced a 1-second window and F1 0.563 on IS1008a.D (9 matches, 16 predictions, 16 references). These two recordings have been repeatedly used for development, the underlying Uhm model used AMI in training, and this small cross-check is not final validation. The two-boundary tolerance remained 250 ms. The official AMI test set remains unopened. Candidate scripts and weights are temporary, and the agreement approach has not been integrated into the app.

### Additional AMI training-partition transfer checks

Applied both previously selected agreement windows, unchanged, to full ES2010a.A and IS1003a.A recordings. The 0.1-second window scored 0.7333 F1 on ES2010a.A (11 matches, 12 predictions, 18 references) and 0.2500 on IS1003a.A (3 matches, 6 predictions, 18 references). Pooled F1 is 0.5185 (14 matches, 18 predictions, 36 references). The 1-second window scored 0.6471 and 0.2500 respectively. Both are AMI training-partition speakers and Uhm's exact AMI training overlap is unknown. The first recording exceeds 0.70, but the second has low recall and the pooled result does not. Neither validates a generalizable 0.70 detector.

The ES2008a.A video output retains per-frame face/hand detection and aggregated pose metrics, but it does not preserve the per-frame pose coordinates needed to compare most temporal movement features against reference events. AMI's gesture annotation describes communicative events and off-camera intervals, not exhaustive facial landmark visibility. The current per-frame tracking coverage cannot be interpreted as landmark accuracy or as 15 validated video features. A suitable labeled video benchmark or explicit new annotation protocol is needed for those measures.

### Error breakdown and candidate recovery

On ES2010a.A, the Switchboard acoustic detector matched 11 of 18 references without class restrictions, the Uhm recall spans matched 15, and their union matched 15. On IS1003a.A the corresponding counts were 9, 7, and 10 out of 18. These counts use the unchanged 250 ms boundary criterion and ignore um/uh class. The candidate sets therefore have partial complementarity, but IS1003a.A still has at least eight reference events outside their union at this tolerance.

Tested allowing a high-confidence Switchboard-only event alongside the 0.1-second Uhm agreement rule. For each of four development/training speakers, chose a threshold from 0.5, 0.6, 0.7, 0.8, 0.9, and 1.01 on the other three speakers, then scored the held-out speaker. Every fold selected 1.01, which retains only agreement events. Fold F1 scores were 0.733, 0.250, 0.563, and 0.524. This small, repeatedly used set and unknown upstream Uhm training overlap limit inference. A simple confidence rescue did not improve the training folds and was not promoted.

Added an opt-in `--pose-timeline` output that preserves timestamped normalized pose coordinates and explicit missing frames for offline video benchmarks. On a real 60-second ES2008a close-up excerpt, the CLI returned 300 ordered frames, all with pose detections. This is an integration/coverage check and does not measure landmark accuracy. Seven focused video tests and all 66 repository tests passed.

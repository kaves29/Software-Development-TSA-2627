# Speakly analysis progress

## 2026-11-25

- Audited the existing analysis modules and the research handoff. Audio uses speech and word timing, acoustic measurements, an optional filler model, and transcript heuristics. The existing transcript-based provider observations are outside this validation scope. Several outputs overlap conceptually, so counting fields overstates validated feature count.
- Video already includes pose observations, optional hand and face models, a background similarity transform, and visible hand-to-face intervals and return counts. Existing tests exercise controlled transformations and landmark sequences. Real speaking video with labeled behaviors is still needed.
- Session aggregation preserves individual results and missing evidence. It does not provide a benchmarked shared audio/video timeline or fusion features.
- The checkout has the earlier package and handoff renames as local changes. No audio or video recordings were found in the workspace file inventory.
- Review media licensing and feature label coverage before acquiring data. AMI is a candidate for fully recorded meeting speech and synchronized video, but would need new labels for most visual and fusion tasks. PodcastFillers is useful for reproducing filler experiments, with research-use limits and incomplete candidate labels. DisfluencySpeech is useful for parser development, with limited speaker diversity and acted speech.
- Reproduced a clean 61-test baseline after resolving missing dependencies in an isolated CPU environment. Verified the AMI annotation archive, its checksum, and meeting-level label availability. No new held-out feature scores were produced.

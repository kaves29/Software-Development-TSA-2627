# Speakly analysis goals

Prioritize validation of 15 distinct audio features and 15 distinct video features. The owner has deferred multimodal feature optimization and validation for now. Use complete English speaking recordings. The current owner-requested minimum is 0.70 for each feature and for the system, with 0.80 as the working target. The prior multimodal target was ten features; revisit it only after the separate pipelines. Website, live capture, OpenAI, and roadmap work require separate approval after analysis validation.

## Benchmark acceptance protocol

- Freeze feature definitions, tolerances, labels, exclusions, and the split before optimization. Keep speakers and source recordings disjoint across splits, including derived clips. Keep the final labels separate from model and threshold development.
- Use pooled event F1 for event features, with one-to-one matches, class agreement, and both endpoints within 250 ms as the initial event rule. Report precision, recall, false alarms per minute, and boundary error. Review the tolerance against annotator agreement before freezing it.
- Use macro F1 for categorical features. For continuous measurements and landmark tracking, define a tolerance in meaningful units before tuning and use the fraction within tolerance, alongside absolute error. Freeze a separate tolerance for each such feature before it can pass.
- Use all eligible labeled units as the denominator for tolerance scores. For event and classification scores, count unavailable predictions as misses when there is labeled evidence. Report coverage and uncertainty by resampling speakers. Disclose missing reference labels, and do not count a feature as validated when it has no independent labeled positives.
- Compare fusion to both single-modality baselines on the same recordings, with the same labels and scoring rules. Report alignment errors and show incremental value from combining modalities.
- Freeze predictor and scorer revisions, source terms, recording hashes, split identifiers, label provenance, and commands. Keep recordings, credentials, and restricted artifacts private.

Deferred candidate fusion tasks include visible speech timing versus voiced segments, gesture timing versus speech onset, gesture overlap with pauses, gesture timing around pitch accents, and nod timing during speaking versus listening. These are candidates pending an observable definition, independent labeling, and baseline comparisons.

For an overall descriptive result, report the unweighted mean of the frozen per-feature scores from the end-to-end held-out run. Require at least 0.70 overall and on every individual feature. An unscored feature leaves the overall gate unresolved. Score outputs from the normal analysis entry point on complete recordings, including abstentions.

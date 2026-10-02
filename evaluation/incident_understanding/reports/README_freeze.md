# Experiment freeze

The held-out `test` split was not read until this configuration was frozen.

- Baseline: `app.ml.baseline.RuleBaseline` (deterministic ES/PT regex rules).
- Primary model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Challenger: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`.
- Classifier: multinomial `LogisticRegression(max_iter=1000, random_state=42)`.
- Selected confidence threshold: `0.7` (chosen on DEV; accepted accuracy stays 1.0 across the
  plateau 0.5-0.75, coverage begins to drop at 0.65+).
- Dataset: synthetic, `seed=42`, group-aware split stratified by label (`dataset.json` v1.0.0).

`freeze_config.json` is machine-readable. Any change to model, threshold, seed, label set or
split requires a new freeze before the test split is consulted again.

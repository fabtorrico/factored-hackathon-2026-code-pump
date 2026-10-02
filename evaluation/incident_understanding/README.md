# Phase 4A - Multilingual incident classification evaluation

Team-generated **synthetic** dataset (no organizer records, no PII) used to evaluate a single
learned component for the *customer-reported* incident class, against a deterministic rule
baseline. This component is **not wired into the production workflow** (that is Phase 4B).

## Labels (customer-reported, never banking truth)

- `PENDING_OR_DELAYED`
- `FAILED_OR_DECLINED`
- `REVERSED`
- `APPROVED_BUT_UNRESOLVED`
- `AMBIGUOUS_TRANSACTION`
- `OUT_OF_SCOPE`

## Dataset

- `dataset.json` - all examples plus the three splits and metadata.
- `splits.json` - the semantic-family ids assigned to each split (leakage audit).
- Generator: `scripts/generate_dataset.py` (deterministic, `seed = 42`).
- Each example: `id`, `text`, `language` (`es` | `pt`), `label`, `semantic_family`, `difficulty`.
- Variants of the same intent/paraphrase share a `semantic_family`, so a family never crosses
  a split boundary (no train/test leakage).

### Splits

The split is **group-aware by semantic family and stratified by label**: families are never
shared across splits, and every one of the six labels appears in `train`, `dev` and `test`
(verified in `backend/tests/test_ml_phase4a.py`). A purely global family split can leave a class
out of a split entirely; this stratified scheme prevents that.

| split | examples | families |
| ----- | -------- | -------- |
| train | 145      | 40       |
| dev   | 39       | 11       |
| test  | 40       | 11       |
| total | 224      | 62       |

Exact duplicate `(language, text)` variants inside a family are dropped, and every example id is
unique (regression-tested).

## Evaluation protocol (frozen)

1. Baseline is frozen (deterministic regex rules, `app.ml.baseline.RuleBaseline`).
2. Models compared on **DEV only** (MiniLM vs MPNet); threshold chosen on **DEV only**.
3. Config frozen (`reports/freeze_config.json`) **before** the held-out test is read.
4. `test` evaluated once with the frozen config. No test-driven changes.

Selected config: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` + multinomial
`LogisticRegression(max_iter=1000, random_state=42)`, confidence threshold `0.7`.

## Results

DEV (model/threshold selection, n = 39):

| system                     | accuracy | macro-F1 | coverage | abstained |
| -------------------------- | -------- | -------- | -------- | --------- |
| rule baseline (frozen)     | 1.000    | 1.000    | 1.000    | 0         |
| learned (MiniLM, th=0.7)   | 0.795    | 0.876    | 0.795    | 8         |

Held-out TEST (n = 40):

| system                     | accuracy | macro-F1 | coverage | abstained |
| -------------------------- | -------- | -------- | -------- | --------- |
| rule baseline (frozen)     | 0.875    | 0.937    | 0.875    | 5         |
| learned (MiniLM, th=0.7)   | 0.750    | 0.778    | 0.750    | 10        |

Learned per-language TEST macro-F1: `es` 0.778, `pt` 0.778.

**Zero misclassifications.** Every single error in both systems is an **abstention**, not a wrong
label: accepted accuracy is 1.000 for both. The learned model abstains on two low-confidence
clusters, `APPROVED_BUT_UNRESOLVED` and `OUT_OF_SCOPE`
(see `reports/error_analysis.json`).

## Honest finding: the baseline wins

On this dataset the **deterministic rule baseline outperforms the learned model** on both DEV
(1.000 vs 0.876 macro-F1) and TEST (0.937 vs 0.778 macro-F1). The synthetic families embed the
baseline's own keywords almost verbatim, which flatters the regex rules, while the embedding
model stays under-confident and abstains too often at `th = 0.7`. Lowering the threshold to `0.5`
on DEV keeps accepted accuracy at 1.000 and raises coverage (0.923), but the trained model still
brings no demonstrated accuracy advantage here.

**Do not read these numbers as real-world readiness, and do not wire this model into the
workflow.** A trustworthy signal requires harder, more realistic, more adversarially-diverse data
(and likely a task-specific model or fine-tuning) before any Phase 4B decision.

A follow-up audit quantified the lexical bias: 100% of DEV and 87.5% of TEST examples contained the
exact regex cue of their gold class, and the baseline scored 1.000 accuracy whenever the cue was
present and 0.000 whenever it was absent. The v1 "baseline wins" result is therefore largely a
construction artifact. This limitation motivated the independently authored Challenge Set v2
(`../incident_understanding_v2/README.md`).

## Reproduce

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\generate_dataset.py
.venv\Scripts\python.exe ..\evaluation\incident_understanding\run_evaluation.py
```

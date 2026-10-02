# Incident Understanding - Challenge Set v2

Independently authored, multilingual (ES/PT) challenge set used to stress-test the two
**frozen v1** Phase 4A systems:

- deterministic baseline: `app.ml.baseline.RuleBaseline`
- learned model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` +
  `LogisticRegression(max_iter=1000, random_state=42)`, confidence threshold `0.7`

v2 is a **new, harder distribution**. It is not derived from v1 and was authored without
looking at model predictions. The v1 artifacts remain frozen and untouched.

## Why v2 exists

The v1 audit found the v1 test set materially favored the baseline: 100% of DEV examples
(and 87.5% of TEST examples) contained the exact regex cue of their gold class, and the
baseline scored 1.000 accuracy whenever the cue was present and 0.000 when it was absent.
v1 was therefore too easy and too lexically aligned with the baseline to support a
deployment decision. v2 removes that alignment.

## System and data provenance

- **Organizer-provided banking data**: curated DuckDB (`/data/`, gitignored) -> banking core ->
  deterministic policy engine. Not used by this experiment.
- **Team-generated synthetic ML evaluation data**: v1 `dataset.json` and v2 `challenge.json`
  (no organizer records, no PII).
- **Pretrained multilingual embedding model**: `paraphrase-multilingual-MiniLM-L12-v2`
  (third-party weights, downloaded to a local HF cache, never committed).
- **Trained lightweight classifier**: scikit-learn `LogisticRegression`, fit on v1 TRAIN only.

## Design

- 6 semantic classes (no `ABSTAIN` class): `PENDING_OR_DELAYED`, `FAILED_OR_DECLINED`,
  `REVERSED`, `APPROVED_BUT_UNRESOLVED`, `AMBIGUOUS_TRANSACTION`, `OUT_OF_SCOPE`.
- 150 semantic families x 4 variants = **600 examples**, **100 per class**.
- Languages: **312 ES / 288 PT**; each family is single-language.
- 6 difficulty tiers (see `metadata.tier_definitions`): `DIRECT`, `INDIRECT`,
  `HARD_NEGATIVE`, `LEXICAL_OVERLAP`, `COLLOQUIAL_OR_NOISY`, `LOW_CONTEXT`.
- `AMBIGUOUS_TRANSACTION` is a semantic class (the customer cannot identify which of
  several transactions is at fault); it is not model abstention.

Authoring rules enforced by the generator:

- no copying/paraphrasing v1 TEST; normalized duplicate and token-Jaccard >= 0.85
  near-duplicate checks against all 40 v1 TEST items;
- ES and PT authored independently (not machine translations);
- unique ids, unique normalized `(language, text)`, per-family label/language/tier
  consistency, non-empty text, ES/PT balance, >= 30 per class, all tiers present.

## Freeze

Frozen **before any model was run on v2** (see `reports/freeze_v2.json`):

- version: `2.0.0`
- artifact: `challenge.json`
- sha256: `f571726ad934e87e7d0663776071cdacfc2b922a882b9960143708362bdedc26`
- seed: `42`; `frozen_before_any_model_run: true`

Regenerating the set is deterministic and reproduces the same hash.

## Protocol

`evaluate_v2.py`:

1. verifies the `challenge.json` hash against `reports/freeze_v2.json`;
2. confirms the frozen systems are unchanged (model name, classifier, params, threshold);
3. reconstructs the learned model by fitting **only on v1 TRAIN** (145 examples). Challenge
   Set v2 is **never used for training or tuning** of any system; it is evaluation-only;
4. evaluates baseline, learned raw (`threshold=0.0`) and learned operational
   (`threshold=0.7`) and writes comparative / per-class / per-language / per-tier /
   error-analysis reports.

## Results (n = 600)

| System | Accuracy | Macro-F1 | Coverage | Accepted acc. | Abstention |
| --- | --- | --- | --- | --- | --- |
| Baseline | 0.248 | 0.308 | 0.328 | 0.756 | 0.672 |
| Learned, raw (th=0.0) | 0.582 | 0.591 | 1.000 | 0.582 | 0.000 |
| Learned, operational (th=0.7) | 0.247 | 0.361 | 0.287 | 0.860 | 0.713 |

Per tier (accuracy / coverage):

| Tier | n | Baseline acc | Learned raw acc | Learned th=0.7 acc (cov) |
| --- | --- | --- | --- | --- |
| DIRECT | 128 | 0.289 | 0.719 | 0.328 (0.35) |
| INDIRECT | 112 | 0.259 | 0.607 | 0.232 (0.25) |
| HARD_NEGATIVE | 104 | 0.202 | 0.365 | 0.087 (0.21) |
| LEXICAL_OVERLAP | 64 | 0.234 | 0.703 | 0.375 (0.41) |
| COLLOQUIAL_OR_NOISY | 96 | 0.240 | 0.510 | 0.167 (0.17) |
| LOW_CONTEXT | 96 | 0.250 | 0.594 | 0.323 (0.36) |

Per language (accuracy): baseline ES 0.253 / PT 0.243; learned raw ES 0.571 / PT 0.594.

Baseline per-class F1 is near zero for `APPROVED_BUT_UNRESOLVED` (0.02),
`OUT_OF_SCOPE` (0.10), `FAILED_OR_DECLINED` (0.25) and `PENDING_OR_DELAYED` (0.29), and is
only strong on `AMBIGUOUS_TRANSACTION` (0.91, whose cue `"no se"/"nao sei"` is explicit and
appears verbatim). Its v1 near-perfect score was a construction artifact.

## Error analysis (learned, th=0.7)

452 errors, of which **428 are low-confidence abstentions** (71% of all traffic). The
remaining 24 are genuine confusions: `REVERSED -> FAILED_OR_DECLINED` (9),
`AMBIGUOUS_TRANSACTION -> FAILED_OR_DECLINED` (5),
`OUT_OF_SCOPE -> FAILED_OR_DECLINED` (5), `FAILED_OR_DECLINED -> APPROVED_BUT_UNRESOLVED` (4),
plus a few borderline cases. Abstentions are spread across every class (51-91 each), so
this is not a single-class calibration bug: the learned model is genuinely uncertain on the
harder, more diverse phrasing.

## Comparison with v1

| | v1 TEST (n=40) | v2 (n=600) |
| --- | --- | --- |
| Baseline accuracy | 0.875 | 0.248 |
| Baseline coverage | 0.875 | 0.328 |
| Learned raw accuracy | 0.850 | 0.582 |
| Learned th=0.7 accuracy | 0.750 | 0.247 |

Both systems collapse on v2. The baseline collapses hardest because it depends on literal
cue words; the learned model degrades more gracefully but is still far from usable.

## Recommendation

**D - neither system is reliable enough to deploy.** Do not wire either into
`POST /api/incidents` (that remains Phase 4B and is gated on this result).

Rationale:

- Baseline-only (A): 67% abstention and 24.8% accuracy on realistic phrasing. Its v1
  performance was an alignment artifact; leaning on it would silently escalate most
  incidents.
- Learned-only (B): 58.2% raw accuracy is well below a safe operational bar; at the frozen
  0.7 threshold it abstains on 71% of traffic (accepted accuracy 86% on a third of cases).
- Hybrid (C): would need a calibrated router and both components are individually weak, so
  no combination is justified on this evidence.

If Phase 4A is pursued further, the learned path is the only viable direction, but it
requires a much larger, more diverse training set, proper probability calibration, and a
held-out challenge set like this one for every model change. Phase 4A should be considered
**not solved**, and the deterministic baseline should not be presented as production-ready.

Concretely: the next experiment should evaluate a **stronger pretrained language-understanding
component** (a larger multilingual encoder and/or a task-fine-tuned model) against this **frozen
Challenge Set v2**, and only then consider production integration.

## Reproduction

```powershell
# 1. Build and freeze v2 (deterministic; must run before any model)
backend/.venv/Scripts/python evaluation/incident_understanding_v2/generate_challenge_v2.py

# 2. Evaluate the frozen v1 systems on v2
backend/.venv/Scripts/python evaluation/incident_understanding_v2/evaluate_v2.py
```

Tests (from `backend/`):

```powershell
.venv/Scripts/python -m pytest tests/test_ml_challenge_v2.py -q
$env:CODE_PUMP_RUN_ML_MODEL_TESTS="1"; .venv/Scripts/python -m pytest tests/test_ml_challenge_v2.py -q
```

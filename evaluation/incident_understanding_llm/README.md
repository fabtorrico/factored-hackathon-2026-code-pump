# Phase 4B-1 - LLM language-understanding evaluation

Offline evaluation of a stronger pretrained language-understanding component, using the OpenAI
Responses API with strict Structured Outputs.

**No production integration is performed in this phase.** Nothing here touches `IncidentInput`, the
Banking Core, the Policy Engine, the Incident Workflow or `POST /api/incidents`. This area is an
evaluation harness only.

## Status: closed without benchmark results

> **Phase 4B-1 harness complete; external LLM benchmark blocked by unavailable API credits; no LLM
> model promoted.**

Phase 4A showed that the deterministic baseline and a MiniLM + Logistic Regression classifier are
both far below usable Spanish/Portuguese incident understanding, so this phase was run to test
whether a stronger pretrained component could clear a pre-registered bar.

| | |
| --- | --- |
| Harness | Complete and validated |
| Prompt, schema, gate, model ids | Frozen before execution, unchanged since |
| `gpt-5.6-luna` benchmark (600 examples) | **Not executed** |
| `gpt-5.6-terra` benchmark (600 examples) | **Not executed** |
| Reason | The API account has no credits |
| Provider response | HTTP 429, `credit_balance_exhausted` / `insufficient_quota` |
| Benchmark requests accepted | 0 |
| LLM quality metrics that exist | None |

The credential was valid and authentication reached the provider; generation was refused for billing
before any example was sent. **No credits were added**, no model identifier was changed, and no other
provider or model was substituted.

Three consequences, stated plainly:

- **No Luna or Terra metrics exist.** Not zero, not estimated, not illustrative. Absent.
- **The quality gate is unobserved** for both candidates. Neither passed it and neither failed it.
- **The billing failure is not a model-quality failure.** It is an infrastructure condition and is
  never scored as one. The fact that MiniLM also fell short in Phase 4A says nothing about these two
  models, and the blocked benchmark does not weaken the Phase 4A evidence, which remains
  authoritative.

No LLM was promoted into the production workflow, and MiniLM was not promoted in its place. The
production application runs with no `OPENAI_API_KEY` and no OpenAI SDK installed.

`reports/execution_status.json` is the machine-readable record. The benchmark remains reproducible
unchanged: add credits and re-run the two commands below. The gate is evaluated on first observation
and stays fixed afterwards, so its pre-registration survives the delay.

Candidates, evaluated against the **frozen** Challenge Set v2:

| Role | Model |
| --- | --- |
| Primary | `gpt-5.6-luna` |
| Challenger | `gpt-5.6-terra` |

The task is to name what the **customer reports**, not to predict banking truth. The model may not
emit a transaction status, a customer identity, authorization, ownership, a policy outcome or any
banking fact, and the schema admits no field that could carry one.

## Layout

| File | Role |
| --- | --- |
| `prompt_contract.py` | Frozen prompt, output schema, model ids, pricing, quality gate, selection rule |
| `challenge_io.py` | Read-only, hash-verified access to Challenge Set v2 |
| `client.py` | The only module that talks to the API; injectable and mockable |
| `metrics.py` | Accuracy, macro P/R/F1, per class / language / tier, gate evaluation, cost |
| `freeze_prompt.py` | Writes `reports/prompt_freeze.json` and `reports/quality_gate.json` |
| `evaluate_llm.py` | Explicit benchmark command (real API) |
| `analyze_errors.py` | Error analysis, comparison and recommendation (never calls the API) |

Challenge Set v2 stays in `../incident_understanding_v2/` and is never written to.

## Frozen output schema

The smallest strict schema that carries the whole task:

```json
{
  "type": "object",
  "properties": {
    "label": {
      "type": "string",
      "enum": [
        "PENDING_OR_DELAYED",
        "FAILED_OR_DECLINED",
        "REVERSED",
        "APPROVED_BUT_UNRESOLVED",
        "AMBIGUOUS_TRANSACTION",
        "OUT_OF_SCOPE"
      ]
    }
  },
  "required": ["label"],
  "additionalProperties": false
}
```

No confidence, no rationale, no evidence, no chain of thought. There is no seventh class: a refusal
or an API failure is recorded separately and never becomes a label.

## Protocol

1. **Freeze first.** `freeze_prompt.py` writes the prompt text, prompt SHA-256, schema, model ids,
   evaluation configuration, the pre-registered quality gate and the model-selection rule. It
   refuses to overwrite an existing freeze.
2. **Verify.** Every run re-verifies `challenge.json` against `reports/freeze_v2.json` and against
   the SHA-256 pinned in `prompt_contract.py`. A mismatch aborts.
3. **One request per example.** Same prompt text, same schema, same `reasoning.effort` for Luna and
   Terra. Only the example text is sent; language, tier and gold label never leave the process.
4. **No tools.** No `tools` argument is sent at all, so web search, file search, code interpreter and
   every other hosted tool are absent by construction rather than switched off. `store=False`.
5. **Record everything.** Per example: id, language, tier, gold, predicted label, model,
   structured-output validity, refusal/API failure, latency, and token usage when the API returns
   it. No hidden reasoning is requested or stored.
6. **Metrics, then errors.** `analyze_errors.py` runs only after the metrics artifacts exist and
   never calls the API.

`temperature` is deliberately not sent: it is not among the supported features of these models and
omitting it avoids a request rejection while keeping the run deterministic.

`max_retries=0` is set explicitly on the SDK client. The SDK retries twice by default, so leaving
it unset would silently retry failed requests and make latency and cost describe something other
than one request per example. An API failure is recorded as an error and the run continues; it is
never retried and never re-queried.

## Pre-registered quality gate

Recorded in `reports/quality_gate.json` **before** any result artifact existed, and never changed
afterwards.

| Criterion | Threshold |
| --- | --- |
| Overall macro-F1 | >= 0.85 |
| Spanish macro-F1 | >= 0.82 |
| Portuguese macro-F1 | >= 0.82 |
| Structured-output validity | >= 0.99 (approximately 100%) |
| Critical systematic class failure | none |

*Critical systematic class failure* is defined in the artifact: an in-scope class (any of the five
classes other than `OUT_OF_SCOPE`) whose F1 is below 0.70, **or** which contributes at least 25% of
all errors while its own F1 is below 0.80.

Passing means **eligible for guarded integration into the hackathon prototype**. It does not mean
production-ready banking AI.

### Model selection

Also frozen up front. If neither passes, no integration. If one passes, that one. If both pass, the
lower-cost model wins unless the other's overall macro-F1 is higher by at least **0.02**
(`MATERIAL_QUALITY_DELTA`).

## Contamination controls

- No Challenge Set v2 example appears in the prompt or the schema. A regression test asserts that no
  example text, and no six-word prefix of one, occurs in the prompt.
- Challenge Set v2 is read-only. It is hash-verified on every read and never written, relabeled,
  regenerated or reduced.
- Challenge Set v2 is never used for training, tuning or few-shot demonstration.
- The prompt was frozen before any model call, and is byte-identical for Luna and Terra.
- No prompt or model change is permitted after results are observed.

Provenance of the prompt wording: the six class definitions and the tie-breakers come from the
Phase 4A label domain (`app/ml/labels.py`) and the already-frozen Phase 4A error analysis on
Challenge Set v2; the out-of-scope subject list is the frozen baseline's own keyword domain in
`app/ml/baseline.py`. No LLM run informed them.

## Reproduce

Blocked until the OpenAI account has available credits. Nothing below has changed; the protocol is
still exactly as frozen.

```powershell
# 1. dependency (evaluation-only extra; the runtime does not need it)
backend/.venv/Scripts/python -m pip install -e "backend[evaluation]"

# 2. freeze the prompt, schema, config and gate BEFORE any model is called
#    (already done; the script refuses to overwrite an existing freeze)
backend/.venv/Scripts/python evaluation/incident_understanding_llm/freeze_prompt.py

# 3. set the credential in the environment (never in source, never committed, never in reports)
$env:OPENAI_API_KEY = "..."

# 4. benchmark, one model at a time, all 600 frozen examples
backend/.venv/Scripts/python evaluation/incident_understanding_llm/evaluate_llm.py --model gpt-5.6-luna
backend/.venv/Scripts/python evaluation/incident_understanding_llm/evaluate_llm.py --model gpt-5.6-terra

# 5. error analysis, comparison and recommendation
backend/.venv/Scripts/python evaluation/incident_understanding_llm/analyze_errors.py
```

`--limit N` is available for a smoke test, but it marks the run incomplete so a partial run can
never be mistaken for the benchmark or pass the gate.

## Artifacts

Written to `reports/`, all small and reproducible:

- `prompt_freeze.json`, `quality_gate.json` (written before the run)
- `execution_status.json` (closure record: harness complete, benchmark not executed)
- `predictions_<model>.json`, `metrics_<model>.json`, `gate_<model>.json`, `cost_<model>.json`
- `error_analysis_<model>.json`, `comparison.json`

Only the first three exist today. The per-model artifacts are absent because no benchmark response
was ever accepted, and no placeholder of any of them was written.

No API key is stored in any artifact.

## Limitations

- **There is no LLM quality evidence.** The recorded cost of this phase is a complete harness with no
  measured model quality. The gate stays unobserved rather than being estimated.
- The evaluation set is team-generated synthetic data, not organizer records. Even once measured,
  passing the gate would demonstrate capability on this distribution, not on real customer traffic.
- Cost and latency depend on observed token usage and on published prices that OpenAI has repriced
  before; a rerun may cost differently. The frozen rates predate the eventual measurement.
- Latency figures, once measured, come from a single sequential pass with no concurrency, so they
  describe this harness, not a deployed service's throughput.

## Tests

```powershell
Set-Location backend
.venv/Scripts/python -m pytest tests/test_ml_llm_phase4b1.py -q
```

The suite covers the strict schema, all six labels, refusal and API-failure handling, evaluation
artifact parsing, challenge hash validation, v2 immutability, and that the client boundary is fully
mockable. `OPENAI_API_KEY` is removed for the duration of the module, so no default test can reach
the API even by accident. Real API evaluation is only the explicit `evaluate_llm.py` command.
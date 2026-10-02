# Phase 6 - system safety, robustness and end-to-end evaluation

End-to-end evaluation of the **whole running system** (not a single model): FastAPI banking core,
policy engine, incident workflow, operational store, agent workspace and the frontend safety
contract. It is a higher-level scenario/report layer over the application; it intentionally does
not duplicate every `pytest` assertion.

This is **prototype safety and robustness evidence, not production assurance.** It runs entirely
in-process, offline, without `OPENAI_API_KEY` and without mutating the repository's `data/` tree.

## What it exercises

| Category | Focus |
| --- | --- |
| A. Authentication | missing / unknown / expired / blank credentials; session id never echoed |
| B. Authorization | cross-customer reads reported as not-found; scoped candidate search |
| C. Agent boundary | agent credential vs customer session; read-only agent surface |
| D. Incident contract | exactly one identification mode; strict typing; unknown filter key refused |
| E. Identification | exact match, ambiguity, no match, ownership; candidates carry no identity |
| F. Policy matrix | precedence (session > scope > tool > evidence > identification > status), all statuses, determinism, version pin |
| G. Grounding | no inferred decline cause, no money-movement claim, verbatim curated evidence |
| H. Missing evidence | absent curated values read back absent, never fabricated |
| I. Tool failure | missing curated DB is a 503; failed writes never disguised as escalations |
| J. Act -> Verify | completed escalation implies persisted, re-readable case + handoff |
| K. Persistence | case/handoff/events survive reopen; schema init is idempotent |
| L. Handoff | request restated, verified facts, actions, pinned policy, safe route |
| M. Audit | one event per tool call, denied reads audited, no credential in events |
| N. PII safety | no raw PII in curated tables/responses; `.env` and `data/` ignored |
| O. API robustness | unknown path/method/params, malformed JSON, empty body |
| P. Frontend contract | copy hides policy internals; agent client read-only; credentials header-only |
| Q. AI status | runtime makes no LLM call; LLM benchmark documented as not executed |
| R. Adversarial | instruction-like prose/SQL/unicode cannot select a verdict or identity |
| S. Concurrency | repeated escalations are distinct persisted cases; stable reads |
| E2E. Live curated | seven real scenarios against the curated DuckDB, plus agent visibility |
| PERF. Latency | local p50/p95 over a small sample (prototype evidence, not an SLA) |

## Run

From the repository root:

```powershell
backend\.venv\Scripts\python.exe evaluation\system\run_evaluation.py
```

Exit code is `1` if any case fails. No network, no API key, no writes outside a temporary
directory that is removed afterwards.

## Artifacts

- `evaluation_cases.json` - declarative catalogue of every case (id, category, scenario,
  expected behavior, severity-if-failed).
- `report.json` - machine-readable totals, per-category scorecard, latency, per-case results.
- `report.md` - human-readable scorecard, latency table, failures and the full case list.

## Result

Latest run: **125 cases, 125 PASS, 0 FAIL, 0 SKIP** (all categories above).

## Defect found and fixed during Phase 6

`D06 Unknown filter key`: the nested `CandidateFilters` model accepted and silently dropped unknown
keys in an incident body (e.g. `{"filters": {"transaction_staus": "Declined"}}`), which would widen
a search beyond what the caller asked for. It now sets `extra="forbid"` so the request is rejected
with `422`; the query routes pop the session `customer_id` scope key before constructing the model.
Regression tests: `backend/tests/test_workflow_api.py::test_unknown_filter_key_is_rejected` and
`backend/tests/test_api.py::test_api_candidates_enforce_scope`.

## Limitations (honest)

- Latency numbers are a small local sample, **not** an SLA.
- Category R tests the structural boundary (no field can carry instructions or verdicts). It is
  **not** a full LLM prompt-injection evaluation, because no LLM runs at runtime (see Q).
- Category Q is a documentation/status check: the Phase 4A baseline is frozen and reproducible, and
  the Phase 4B-1 LLM harness was prepared but the benchmark was not executed (HTTP 429 / no
  credits). That is a recorded fact, not a defect.
- E2E and PERF cases require `data/processed/banking.duckdb`; if it is absent they report `SKIP`.

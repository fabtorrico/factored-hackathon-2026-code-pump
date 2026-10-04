# Code Pump

Transaction/payment incident resolution with controlled automation, deterministic policy, and verified handoffs.

## What problem we solve

Code Pump focuses on transaction/payment incident resolution (Declined, Pending, Reversed, or ambiguous movement reports). Normal resolution requires verified banking facts, consistent policy application, and safe escalation when a human specialist must act. Ambiguity (no match/multiple matches), incomplete information, or approved-but-unresolved cases are handled explicitly rather than inferred. The solution is designed for controlled, auditable automation with strict read-only boundaries and act-then-verify handoffs.

### OBSERVED DATA EVIDENCE (separate from design judgment)

The repository's curated evidence comes from committed synthetic banking data converted to a curated DuckDB. No organizer-provided contact-center demand/complaint-frequency dataset is present or analyzed in the repo. Data engineering (contracts, allowlist projection, quality checks) is documented. The available subset supports a focused workflow around transaction/payment statuses, but it does not establish quantified contact-center volume. **If contact-center demand frequency cannot be established from the supplied data, that is explicitly stated here.** Curated data enables deterministic E2E tests and Phase 6 system evaluation (125/125 PASS).

**WORKFLOW DESIGN JUDGMENT:** transaction/payment incidents are coherent because they require strict ownership/grounding, identity-scoped reads, deterministic rules, and verified escalation paths.

## What Code Pump does

- **Customer path:** report/select movement → verified banking facts → controlled policy decision → resolve / clarify / escalate / abstain (no prose generation, no chain-of-thought exposed).
- **Human specialist path:** verified handoff → facts → evidence → actions taken → unresolved questions → audit timeline (read-only agent workspace; no customer identity exposed in the queue).

## Architecture

Customer Site -> FastAPI -> trusted session -> Banking Core (read-only DuckDB) -> verified facts -> Incident Workflow -> Policy Engine (deterministic) -> RESOLVE/CLARIFY/ESCALATE/ABSTAIN (Act->Verify) -> Operational SQLite (no banking facts copied) -> Agent Workspace (read-only). ML evaluation is offline-only.

## Safety model

- Session-derived identity (X-Session-Id); per-customer auth
- Ownership collapse (foreign/absent treated same)
- Strict schemas (extra=forbid, strict); query param allowlists
- Deterministic policy; unknown statuses escalate; no cause inference from balance/response_code
- Act -> Verify on escalation
- Read-only agent workspace (separate X-Agent-Session-Id)
- PII minimization in curated DB; audit stores session fingerprint only
- Safe failure behavior; no chain-of-thought exposed

## Data engineering

- raw -> staging/temp -> curated DuckDB via explicit column allowlist; contracts validated first
- No silent row dropping/imputation (quality issues reported)
- PII minimization in curated projection
- Deterministic reruns; full-refresh pipeline (not incremental)
- quality_report.json written to data/processed/ on pipeline run (not committed)

## ML / language-understanding evaluation

Phase 4A (ES/PT, 6 labels): baseline vs MiniLM+LogReg. Challenge Set v2 frozen (600 examples; sha256 f571726ad934e87e7d0663776071cdacfc2b922a882b9960143708362bdedc26). Results (v2): baseline acc 0.248, macro-F1 0.308, cov 0.328; learned raw acc 0.582, macro-F1 0.591, cov 1.000; learned (th=0.7) acc 0.247, macro-F1 0.361, cov 0.287. Lexical bias motivated v2; leakage prevention by semantic family/tier. Neither promoted.

## LLM evaluation status

Phase 4B-1: structured-output harness complete; prompt/schema/gate frozen (prompt_sha256 a431bcbdbae3f10e82e9d1cdec9186f00ec63d58d201c9a52db8e83752466077, schema_sha256 c2b09b99a23a026a24f10a2c95e0ec39e42cbbba4b081ff26b428a14f9c8d244). Benchmark NOT executed (execution_status.json: closed_without_results, not_executed; blocker external_api_credits_unavailable, error credit_balance_exhausted, http 429). No LLM promoted.

## Performance

Local prototype measurements (not SLA): declined resolution p50 37.192ms/p95 46.963ms (n=25), pending escalation p50 56.792ms/p95 111.763ms (n=25), agent case detail p50 3.911ms/p95 4.218ms (n=25).

## Cost

Production/demo path is local and deterministic; no external model inference per incident. LLM evaluation cost not observed (benchmark requests blocked before execution). Infrastructure/hosting/ops not measured; cost per successful automated resolution not defined from current evidence.

## Demo scenarios

A - Declined -> RESOLVE; B - Pending -> ESCALATE; C - Reversed -> ESCALATE; D - ambiguous -> CLARIFY. Also approved+unresolved path can escalate/abstain per policy (no dedicated demo profile). Use demo CLI: python -m app.demo status and python -m app.demo reset (operational state only).

## Repository map

backend/app/data, backend/app/banking, backend/app/policy, backend/app/workflow, backend/app/api, backend/app/demo, backend/app/ml, backend/app/agent, frontend, evaluation, scripts, data

## Evaluation artifact index

evaluation/incident_understanding/ (Phase 4A v1)
evaluation/incident_understanding_v2/ (frozen Challenge v2, sha256 f571726ad934e87e7d0663776071cdacfc2b922a882b9960143708362bdedc26)
evaluation/incident_understanding_llm/ (Phase 4B-1 harness/status; not executed)
evaluation/system/ (125-case system eval)

## Frozen artifact confirmation

- Challenge v2: evaluation/incident_understanding_v2/challenge.json sha256 f571726ad934e87e7d0663776071cdacfc2b922a882b9960143708362bdedc26 (matches freeze_v2.json)
- LLM prompt/schema: prompt_sha256 a431bcbdbae3f10e82e9d1cdec9186f00ec63d58d201c9a52db8e83752466077, schema_sha256 c2b09b99a23a026a24f10a2c95e0ec39e42cbbba4b081ff26b428a14f9c8d244
- Phase 4A frozen artifacts unchanged; Phase 6 report: 125/125 PASS

## Route to operation

**OBSERVABILITY:** Current audit events (InMemoryAuditSink) exist; production would require structured logging, metrics, tracing, and durable audit storage.

**RELIABILITY:** Deterministic failure handling, Act->Verify, and no retry in the frozen LLM harness. Bounded retries/timeouts would be needed for any external service calls in production.

**SECURITY:** Trusted demo sessions with authorization boundaries; production requires identity/RBAC, credential management, secret management, and secure session issuance.

**DATA RETENTION:** Local operational SQLite; no formal production retention policy implemented; retention/deletion/archival must be defined before deployment.

**CAPACITY:** Prototype uses local DuckDB + SQLite; no production load/capacity tests performed. Only local latency evidence is available.

**DATA FRESHNESS:** Full-refresh data pipeline (not incremental); no streaming demonstrated. Production refresh cadence and backpressure must be defined.

**LANGUAGE:** ES/PT evaluated experimentally (Phase 4A/v2); no production natural-language classifier is integrated into the runtime path.

**CURRENT STATE:** Code Pump is a validated local prototype.

**CLOUD:** Not currently deployed to cloud.

**CHALLENGE:** Cloud deployment is optional based on organizer clarification.

**DEPLOYMENT:** Local prototype only; cloud deployment is optional, not implemented. The proposed production architecture and remaining work are documented below.

**REMAINING RISKS:** Synthetic prototype policy (not real bank policy), limited transaction sample for some scenarios, no production workforce authentication, no production monitoring/SLA, external LLM benchmark not executed, and other limitations supported by the evidence above.

## How Code Pump addresses the challenge

- **Data-backed problem:** Focused on transaction/payment incidents using committed curated data; contact-center demand frequency not quantified from supplied data (stated explicitly).
- **Functioning system:** Deterministic runtime (API, policy, workflow, banking core, agent workspace, demo) with verified handoffs and Act->Verify.
- **Controlled automation:** Strict authorization/grounding, ownership collapse, extra-forbid schemas, unknown statuses escalate; no LLM in runtime.
- **Data/ML rigor:** Frozen artifacts, leakage-aware evaluation (semantic families/tier), Challenge Set v2 with recorded SHA256; LLM harness frozen but unexecuted.
- **Measured failures:** System evaluation 125/125 PASS; one defect fixed with regression; policy defaults to safe escalation.
- **Route to operation:** Documented operational gaps (observability, retention, capacity, freshness, security, reliability).

## Reproducibility / frozen checks

- Frontend tests: 76 passed. Typecheck/build OK.
- Backend tests: 409 passed, 2 skipped. pytest -W error: OK.
- Ruff check/format: OK.
- Phase 6 system eval: 125/125 PASS (re-run).
- Challenge v2 SHA256 matches freeze_v2.json.
- LLM prompt/schema SHAs recorded; benchmark not executed (documented).
- No secrets/PII/raw data staged; operational artifacts gitignored.

## Dependency/environment notes

- Runtime deps (pyproject): duckdb, fastapi, pydantic-settings, uvicorn[standard]. Python >=3.11,<3.13.
- Dev deps: httpx2, pytest, sentence-transformers, scikit-learn, ruff. httpx2 retained (existing setup; not changed).
- Evaluation extra: openai (optional; only for external LLM harness; not imported by runtime).
- Frontend: Vite/React/TypeScript (see package.json).

**Production behavior unchanged.** This is documentation/packaging only; no features, policy, workflow, ML wiring, or data changed.

# AI-First Banking Incident Resolution

Local prototype for resolving digital transfer and payment incidents using controlled banking tools,
deterministic policy decisions, and human escalation when required.

## Stack

- **Backend:** Python 3.11+, FastAPI, pytest, ruff
- **Frontend:** React, TypeScript, Vite
- **Persistence:** DuckDB for the curated analytical data, SQLite for operational workflow state

## Prerequisites

- Python 3.11 or 3.12
- Node.js 20.19 or newer

## Setup

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e "backend[dev]"
```

```powershell
Set-Location frontend; npm install
```

Copy `.env.example` to `.env` at the repository root to override backend settings. Never commit
`.env`.

`OPENAI_API_KEY` is optional and only needed to re-run the Phase 4B-1 external LLM evaluation. The
application does not read it, and no secret is required to run the backend or its tests.

## Development

```powershell
backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload
```

```powershell
Set-Location frontend; npm run dev
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000` with the prefix stripped.

## Validation

```powershell
Set-Location backend
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
```

```powershell
Set-Location frontend
npm run build
```

## Data

`data/` holds local hackathon data provided by the organizers. It is gitignored and must never be
committed or exposed.

The curated DuckDB database is rebuilt from the CSV sources with:

```powershell
Set-Location backend
.venv/Scripts/python -m app.data
```

This validates the source contracts, loads `customers`, `products` and `transactions` into
`data/processed/banking.duckdb`, and writes `data/processed/quality_report.json`. The run is
deterministic and idempotent. A missing required column or unreadable source fails the run; data
quality problems are reported without modifying the records.

Each curated table is an explicit column allowlist, not a copy of the CSV. The raw files stay
untouched and keep every column, but only the approved columns are projected. Dropped from
`customers`: identity, contact, address and demographic attributes (`document_number`,
`first_name`, `last_name`, `email`, `mobile_phone`, `landline_phone`, `address`, `postal_code`,
`date_of_birth`, `gender`, `occupation`, ...). Dropped from `products`: the customer-facing
`product_number` and `credit_limit`. Dropped from `transactions`: `latitude`, `longitude`,
`is_fraud`, `fraud_score`, `merchant_name`, `merchant_category`, `transaction_category`,
`branch_id`, `transaction_country`, `transaction_city`. Contracts still validate the source
schema before projection, and quality checks run against the full source data.

`products.current_balance` is read-only context. A transaction fails on its recorded
`transaction_status` / `response_code`, never on a balance that looks low.

## Banking core

The backend exposes a small set of typed banking tools over the curated DuckDB database. There is no
query language: every filter maps to one equality or range clause, so a caller cannot widen a read.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/sessions` | Open a trusted demo session for a customer |
| `GET /api/customers/{customer_id}/context` | Customer, products, and transaction counters |
| `GET /api/transactions` | The authenticated customer's transactions |
| `GET /api/transactions/candidates` | Deterministic narrowing on a small closed filter set |
| `GET /api/transactions/{transaction_id}` | One transaction |
| `GET /api/transactions/{transaction_id}/ownership` | Whether the session owns the transaction |
| `GET /api/audit/events` | Recent tool outcomes for the local demo |
| `POST /api/incidents` | Run one structured incident through the policy workflow |

Every protected endpoint requires an `X-Session-Id` header. The session's customer is the only
identity the backend trusts; a `customer_id` in the query is checked, never trusted. Cross-customer
reads return `403`. A transaction the session does not own returns `404`, identical to a transaction
that does not exist, so the endpoint cannot be used to probe for other customers' records. Malformed
or unsupported filters return `400` instead of being silently ignored.

The curated database is opened read-only. Audit events record the tool, outcome, reason, caller,
resource and latency, and store only a short fingerprint of the session id, never the bearer
credential itself or any customer contact data. The demo session store and audit sink are in-memory
and are not a production authentication or logging design.

## Policy engine

Synthetic Banking Policy v1 is an ordered, deterministic decision table. There is no model, no
randomness and no natural-language input: `evaluate_policy(context) -> PolicyDecision` returns one of
`RESOLVE`, `CLARIFY`, `ESCALATE` or `ABSTAIN` with a stable reason code, the rule that decided it and
the policy version. Rules are evaluated in order and the first match wins: `A` invalid or unauthorized
session, `B` out of scope, `C` tool failure, `D` no or multiple candidates, `E` required evidence
missing, `F` declined, `G` pending, `H` reversed, `I` approved with an unresolved issue, `J` approved
with no supported incident, `K` unknown status. Unknown statuses escalate rather than fall through to
a safe-looking default.

The policy is a hackathon demonstration model. It is not a real bank, organizer, settlement or
regulatory policy, and `SupportRoute.PAYMENTS_OPERATIONS` is a synthetic demo route rather than an
organizer-provided structure.

## Incident workflow

`POST /api/incidents` runs one structured incident through the workflow. The request carries no prose,
no policy outcome, no transaction status and no customer identity:

```json
{
  "transaction_id": "TXN-003",
  "filters": { "transaction_type": "Payment", "date_from": "2026-06-17" },
  "in_scope": true,
  "approved_with_unresolved_issue": false
}
```

Exactly one of `transaction_id` or `filters` is required, unknown fields are rejected, and the
authenticated customer comes from the `X-Session-Id` header. The sequence is fixed: validate the
session, identify one or more candidates through the banking tools, map the observed facts into the
policy context, let the policy engine decide, then perform only the permitted action and verify it.

The workflow never reads the curated database itself, never re-derives authorization or ownership, and
never invents a cause. A status can only appear in the policy context because the Banking Core returned
a record owned by the session, and a failed read can only produce a tool failure. Any unrecognized
future status escalates.

| Outcome | Result |
| --- | --- |
| `RESOLVE` | Verified facts only. No customer-facing prose is generated. |
| `CLARIFY` | Zero or several owned candidates are returned for the customer to choose from; nothing is selected automatically. |
| `ESCALATE` | A support case is written, read back, and only then reported as escalated, with a structured handoff of verified facts and the unresolved questions. |
| `ABSTAIN` | Invalid or expired session, out-of-scope incident, or no supported action. No case is created. |

Escalation follows act then verify: the support case is persisted and read back before the workflow
claims success. If the write cannot be read back, the incident is recorded as failed and no escalation
is reported. A support case can never exist without its incident.

Operational state lives in `data/operational/app.db` (gitignored, created on first use,
initialization idempotent): incidents, support cases and workflow events. Banking facts are never
copied into it, and events carry identifiers and stable codes only — no prompts, records or customer
data. Banking endpoints keep their own 401/403/404 behavior; the workflow observes a foreign or absent
transaction identically and cannot be used to probe for another customer's records.

## Status

Phases 3B through 4B-1 are done. Still no AI component in the production path and no frontend work.

| Phase | Outcome |
| --- | --- |
| 3B | Deterministic policy engine, incident workflow, support-case escalation, operational persistence |
| 4A | Challenge Set v2 frozen (600 examples); baseline and MiniLM evaluated. Neither is production-grade |
| 4B-1 | LLM evaluation harness complete. Benchmark **not executed**: no API credits |

### What the language-understanding work established

On frozen Challenge Set v2 (600 examples, ES/PT):

| System | Accuracy | Macro-F1 | Coverage | Abstention |
| --- | --- | --- | --- | --- |
| Deterministic baseline | 0.248 | 0.308 | 0.328 | 0.672 |
| MiniLM + Logistic Regression (raw) | 0.582 | 0.591 | 1.000 | 0.000 |
| MiniLM + Logistic Regression (threshold 0.7) | 0.247 | 0.361 | 0.287 | 0.713 |

Raising the decision threshold buys precision on accepted cases and loses more accuracy than it
gains. **Neither system is approved for production integration**, and Phase 4A remains the
authoritative recorded evidence.

Phase 4B-1 then evaluated whether a stronger pretrained language-understanding component could clear a
pre-registered bar (macro-F1 >= 0.85 overall, >= 0.82 per language, ~100% structured-output validity).
The harness is complete and the gate is frozen, but the benchmark **did not run**: the API account
had no credits and returned HTTP 429 `credit_balance_exhausted` / `insufficient_quota`, so no request
was ever accepted. No LLM metrics exist, the gate is unobserved for both candidates, and no billing
failure was scored as a model-quality failure. Neither `gpt-5.6-luna` nor `gpt-5.6-terra` was
promoted, and MiniLM was not promoted in its place. The benchmark stays reproducible unchanged.

`POST /api/incidents` and everything it reaches are unchanged by 4B-1, and the application runs with
no `OPENAI_API_KEY` and no OpenAI SDK installed. See
[`evaluation/incident_understanding_llm/README.md`](evaluation/incident_understanding_llm/README.md).

# AI-First Banking Incident Resolution

Local prototype for resolving digital transfer and payment incidents using controlled banking tools,
deterministic policy decisions, and human escalation when required.

## Stack

- **Backend:** Python 3.11+, FastAPI, pytest, ruff
- **Frontend:** React, TypeScript, Vite
- **Persistence (later phases):** SQLite for operational state, DuckDB for analytical data

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

Copy `.env.example` to `.env` at the repository root to override backend settings. No secrets are
required in this phase; never commit `.env`.

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

## Status

Phase 1A — local data foundation. No banking logic, policy engine, or AI integration yet.

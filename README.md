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

## Status

Phase 0 — project foundation. No banking logic, policy engine, or AI integration yet.

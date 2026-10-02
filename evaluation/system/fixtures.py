"""Shared fixtures for the Phase 6 system evaluation.

Everything here is built on top of the same building blocks the backend test suite uses, so the
evaluation exercises the real application rather than a re-implementation of it:

- the synthetic source rows come from `backend/tests/conftest.py` (organizer headers and all, so
  the curated projection is proven to drop PII);
- the curated DuckDB database is built by the real `app.data.pipeline.run_pipeline`;
- the API surface is the real FastAPI app with the same dependency overrides the tests use.

No network, no `OPENAI_API_KEY`, no mutation of the repository's `data/` tree: every operational
store and every curated database lives under a temporary directory.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
for _path in (str(BACKEND), str(BACKEND / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import conftest  # noqa: E402  (canonical synthetic row builders)
from app.agent import AgentSessionStore, AgentWorkspace  # noqa: E402
from app.api.dependencies import (  # noqa: E402
    get_agent_workspace,
    get_banking_service,
    get_demo_database_path,
    get_incident_workflow,
)
from app.banking.audit import InMemoryAuditSink  # noqa: E402
from app.banking.repository import CuratedBankingRepository  # noqa: E402
from app.banking.service import BankingService  # noqa: E402
from app.banking.sessions import SessionStore  # noqa: E402
from app.data.pipeline import run_pipeline  # noqa: E402
from app.main import create_app  # noqa: E402
from app.workflow.orchestrator import IncidentWorkflow  # noqa: E402
from app.workflow.storage import OperationalStore, OperationalStoreError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

customer_row = conftest.customer_row
product_row = conftest.product_row
transaction_row = conftest.transaction_row
CUSTOMERS_SOURCE_HEADER = conftest.CUSTOMERS_SOURCE_HEADER
PRODUCTS_SOURCE_HEADER = conftest.PRODUCTS_SOURCE_HEADER
TRANSACTIONS_SOURCE_HEADER = conftest.TRANSACTIONS_SOURCE_HEADER
FakeClock = conftest.FakeClock

OWNER = "CUST-001"
OTHER = "CUST-002"
ABSENT_CUSTOMER = "CUST-404"
SESSION_TTL = timedelta(minutes=30)
FIXED_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)

REAL_DATABASE = ROOT / "data" / "processed" / "banking.duckdb"


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_source_csvs(root: Path, rows: dict[str, list[list[str]]]) -> Path:
    _write_csv(root / "raw" / "customers.csv", CUSTOMERS_SOURCE_HEADER, rows["customers"])
    _write_csv(root / "raw" / "products.csv", PRODUCTS_SOURCE_HEADER, rows["products"])
    _write_csv(
        root / "sample" / "transactions_20260617.csv",
        TRANSACTIONS_SOURCE_HEADER,
        rows["transactions"],
    )
    return root


def synthetic_rows() -> dict[str, list[list[str]]]:
    """A curated dataset with one owned row for every workflow outcome the policy defines."""

    return {
        "customers": [
            customer_row(customer_id=OWNER, segment="Retail", detected_accent="colombian"),
            customer_row(
                customer_id=OTHER,
                segment="Premium",
                detected_accent="argentine",
                email="second.owner@example.com",
                mobile_phone="+54 11 5555 0000",
            ),
        ],
        "products": [
            product_row(product_id="PROD-001", customer_id=OWNER, product_type="Checking"),
            product_row(product_id="PROD-002", customer_id=OTHER, product_type="CreditCard"),
        ],
        "transactions": [
            transaction_row(
                transaction_id="TXN-DECL",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Payment",
                transaction_status="Declined",
                response_code="51",
                amount="40.00",
                amount_usd="40.00",
            ),
            transaction_row(
                transaction_id="TXN-PEND",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Transfer",
                transaction_status="Pending",
                response_code="",
                amount="900.00",
                amount_usd="",
            ),
            transaction_row(
                transaction_id="TXN-REV",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Payment",
                transaction_status="Reversed",
                response_code="",
                amount="40.00",
                amount_usd="40.00",
            ),
            transaction_row(
                transaction_id="TXN-OK",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Purchase",
                transaction_status="Approved",
                response_code="00",
                amount="20.00",
                amount_usd="20.00",
            ),
            transaction_row(
                transaction_id="TXN-WEIRD",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Purchase",
                transaction_status="Processing",
                response_code="",
                amount="10.00",
                amount_usd="",
            ),
            transaction_row(
                transaction_id="TXN-AMB-A",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Deposit",
                transaction_status="Approved",
                currency="COP",
                amount="100.00",
                amount_usd="",
            ),
            transaction_row(
                transaction_id="TXN-AMB-B",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Deposit",
                transaction_status="Approved",
                currency="COP",
                amount="200.00",
                amount_usd="",
            ),
            transaction_row(
                transaction_id="TXN-OTHER-DECL",
                customer_id=OTHER,
                product_id="PROD-002",
                transaction_type="Payment",
                transaction_status="Declined",
                response_code="51",
                amount="40.00",
                amount_usd="40.00",
            ),
        ],
    }


def build_curated_database(root: Path) -> Path:
    write_source_csvs(root, synthetic_rows())
    return run_pipeline(root).database_path


class FailingCaseStore(OperationalStore):
    """Every support-case write fails, so no escalation can ever be verified."""

    def create_support_case(self, case):  # type: ignore[override]
        raise OperationalStoreError("simulated support-case write failure")


class FailingHandoffStore(OperationalStore):
    """The case is written but the handoff write fails, so the escalation is unverified."""

    def save_handoff(self, handoff, created_at):  # type: ignore[override]
        raise OperationalStoreError("simulated handoff write failure")


class SilentHandoffStore(OperationalStore):
    """The handoff write succeeds but the read back cannot see it."""

    def get_handoff(self, case_id):  # type: ignore[override]
        return None


@dataclass
class System:
    name: str
    root: Path
    database_path: Path
    clock: FakeClock
    service: BankingService
    sessions: SessionStore
    audit: InMemoryAuditSink
    store: OperationalStore
    workflow: IncidentWorkflow
    workspace: AgentWorkspace
    client: TestClient

    def open_customer_session(self, customer_id: str) -> str:
        return self.service.create_session(customer_id).session_id

    def open_agent_session(self) -> str:
        response = self.client.post("/api/agent/sessions")
        assert response.status_code == 201, response.text
        return response.json()["agent_session_id"]


def make_system(
    root: Path,
    name: str,
    *,
    database_path: Path,
    demo_database_path: Path | None = None,
    repository=None,
    store: OperationalStore | None = None,
    clock: FakeClock | None = None,
) -> System:
    root.mkdir(parents=True, exist_ok=True)
    clock = clock or FakeClock(FIXED_NOW)
    sessions = SessionStore(ttl=SESSION_TTL, clock=clock)
    audit = InMemoryAuditSink()
    repo = repository if repository is not None else CuratedBankingRepository(database_path)
    service = BankingService(repository=repo, sessions=sessions, audit=audit, clock=clock)
    store = store if store is not None else OperationalStore(root / f"{name}.db")
    store.initialize()
    workflow = IncidentWorkflow(service=service, store=store, clock=clock)
    workspace = AgentWorkspace(store=store, sessions=AgentSessionStore(clock=clock))

    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: service
    app.dependency_overrides[get_incident_workflow] = lambda: workflow
    app.dependency_overrides[get_agent_workspace] = lambda: workspace
    app.dependency_overrides[get_demo_database_path] = lambda: demo_database_path or database_path
    client = TestClient(app)
    return System(
        name=name,
        root=root,
        database_path=database_path,
        clock=clock,
        service=service,
        sessions=sessions,
        audit=audit,
        store=store,
        workflow=workflow,
        workspace=workspace,
        client=client,
    )


def make_synthetic_system(root: Path) -> System:
    database = build_curated_database(root / "curated")
    return make_system(root, "synthetic", database_path=database)


def make_no_data_system(root: Path) -> System:
    absent = root / "absent" / "banking.duckdb"
    return make_system(root, "no_data", database_path=absent)


def make_real_system(root: Path) -> System | None:
    if not REAL_DATABASE.is_file():
        return None
    return make_system(
        root,
        "real",
        database_path=REAL_DATABASE,
        demo_database_path=REAL_DATABASE,
    )


def source_files(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.rglob("*") if path.is_file() and path.suffix in suffixes
    )

import csv
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_banking_service, get_incident_workflow
from app.banking.audit import InMemoryAuditSink
from app.banking.repository import CuratedBankingRepository
from app.banking.service import BankingService
from app.banking.sessions import SessionStore
from app.data.pipeline import run_pipeline
from app.main import create_app
from app.workflow.orchestrator import IncidentWorkflow
from app.workflow.storage import OperationalStore

# The organizers ship every one of these columns. The fixtures reproduce the full source
# headers - PII included - so the curated DuckDB tables are proven to drop them.
CUSTOMERS_SOURCE_HEADER = [
    "customer_id",
    "document_number",
    "document_type",
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "email",
    "mobile_phone",
    "landline_phone",
    "address",
    "city",
    "state",
    "country",
    "postal_code",
    "detected_accent",
    "segment",
    "credit_score",
    "estimated_monthly_income",
    "occupation",
    "marital_status",
    "education_level",
    "registration_date",
    "registration_branch_id",
    "customer_status",
    "last_updated",
    "accepts_marketing",
]

PRODUCTS_SOURCE_HEADER = [
    "product_id",
    "customer_id",
    "product_type",
    "product_number",
    "currency",
    "current_balance",
    "credit_limit",
    "interest_rate",
    "opening_date",
    "expiration_date",
    "opening_branch_id",
    "product_status",
    "opening_channel",
    "has_linked_app",
    "days_past_due",
    "last_transaction_date",
    "last_updated",
]

TRANSACTIONS_SOURCE_HEADER = [
    "transaction_id",
    "transaction_date",
    "process_date",
    "product_id",
    "customer_id",
    "transaction_type",
    "transaction_category",
    "amount",
    "currency",
    "amount_usd",
    "channel",
    "branch_id",
    "merchant_name",
    "merchant_category",
    "transaction_country",
    "transaction_city",
    "transaction_status",
    "response_code",
    "is_fraud",
    "fraud_score",
    "latitude",
    "longitude",
]

CUSTOMER_DEFAULTS: dict[str, str] = {
    "customer_id": "CUST-001",
    "document_number": "G8637940",
    "document_type": "Pasaporte",
    "first_name": "Samuel",
    "last_name": "Diaz Perez",
    "date_of_birth": "1967-06-18",
    "gender": "M",
    "email": "samuel.diaz@example.com",
    "mobile_phone": "+57 315 564 6977",
    "landline_phone": "+57 4 314 5374",
    "address": "Calle 433 #4-21, Barrio Bocagrande",
    "city": "Cartagena",
    "state": "Bolivar",
    "country": "CO",
    "postal_code": "130010",
    "detected_accent": "colombian",
    "segment": "Retail",
    "credit_score": "701",
    "estimated_monthly_income": "24678431.94",
    "occupation": "Administrative",
    "marital_status": "Married",
    "education_level": "University",
    "registration_date": "2021-07-30 05:39:39",
    "registration_branch_id": "SUC-7R3DCC91",
    "customer_status": "Active",
    "last_updated": "2021-08-15 05:39:39",
    "accepts_marketing": "False",
}

PRODUCT_DEFAULTS: dict[str, str] = {
    "product_id": "PROD-001",
    "customer_id": "CUST-001",
    "product_type": "Checking",
    "product_number": "4332181960",
    "currency": "USD",
    "current_balance": "1250.75",
    "credit_limit": "",
    "interest_rate": "0.0",
    "opening_date": "2020-03-18",
    "expiration_date": "",
    "opening_branch_id": "SUC-E1VTXGEU",
    "product_status": "Active",
    "opening_channel": "Web",
    "has_linked_app": "True",
    "days_past_due": "",
    "last_transaction_date": "2025-07-08 17:19:16",
    "last_updated": "2025-12-25 00:57:58",
}

TRANSACTION_DEFAULTS: dict[str, str] = {
    "transaction_id": "TXN-001",
    "transaction_date": "2026-06-17 09:15:00",
    "process_date": "2026-06-17",
    "product_id": "PROD-001",
    "customer_id": "CUST-001",
    "transaction_type": "Transfer",
    "transaction_category": "Wages",
    "amount": "150.00",
    "currency": "USD",
    "amount_usd": "150.00",
    "channel": "App",
    "branch_id": "",
    "merchant_name": "",
    "merchant_category": "",
    "transaction_country": "United States",
    "transaction_city": "Miami",
    "transaction_status": "Approved",
    "response_code": "00",
    "is_fraud": "False",
    "fraud_score": "",
    "latitude": "",
    "longitude": "",
}

Row = Sequence[str | None]


def _build_row(
    header: Sequence[str], defaults: dict[str, str], overrides: dict[str, Any]
) -> list[str]:
    return [str(overrides.get(name, defaults.get(name, ""))) for name in header]


def customer_row(**overrides: Any) -> list[str]:
    return _build_row(CUSTOMERS_SOURCE_HEADER, CUSTOMER_DEFAULTS, overrides)


def product_row(**overrides: Any) -> list[str]:
    return _build_row(PRODUCTS_SOURCE_HEADER, PRODUCT_DEFAULTS, overrides)


def transaction_row(**overrides: Any) -> list[str]:
    return _build_row(TRANSACTIONS_SOURCE_HEADER, TRANSACTION_DEFAULTS, overrides)


def _write_csv(path: Path, header: list[str], rows: Sequence[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


DataRootFactory = Callable[..., Path]


@pytest.fixture
def data_root(tmp_path: Path) -> DataRootFactory:
    def build(
        customers: Sequence[Row] = (),
        products: Sequence[Row] = (),
        transactions: Sequence[Row] = (),
    ) -> Path:
        root = tmp_path / "data"
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "sample").mkdir(parents=True, exist_ok=True)
        _write_csv(root / "raw" / "customers.csv", CUSTOMERS_SOURCE_HEADER, customers)
        _write_csv(root / "raw" / "products.csv", PRODUCTS_SOURCE_HEADER, products)
        _write_csv(
            root / "sample" / "transactions_20260617.csv", TRANSACTIONS_SOURCE_HEADER, transactions
        )
        return root

    return build


@pytest.fixture
def valid_rows() -> dict[str, list[list[str]]]:
    return {
        "customers": [
            customer_row(),
            customer_row(customer_id="CUST-002", segment="Premium", detected_accent="argentine"),
        ],
        "products": [
            product_row(),
            product_row(product_id="PROD-002", customer_id="CUST-002", product_type="CreditCard"),
        ],
        "transactions": [transaction_row()],
    }


OWNER = "CUST-001"
OTHER = "CUST-002"
ABSENT_CUSTOMER = "CUST-404"
SESSION_TTL = timedelta(minutes=30)


@pytest.fixture
def banking_rows() -> dict[str, list[list[str]]]:
    """Two synthetic customers with overlapping types, statuses, dates and amounts.

    Every organizer field is still present in the fixtures (see the *_SOURCE_HEADER tables) so the
    banking reads are exercised against sources that carry PII and prove it never surfaces.
    """
    return {
        "customers": [
            customer_row(customer_id=OWNER, segment="Retail", detected_accent="colombian"),
            customer_row(
                customer_id=OTHER,
                segment="Premium",
                detected_accent="argentine",
                email="second.owner@example.com",
            ),
        ],
        "products": [
            product_row(product_id="PROD-001", customer_id=OWNER, product_type="Checking"),
            product_row(product_id="PROD-002", customer_id=OWNER, product_type="Savings"),
            product_row(product_id="PROD-003", customer_id=OTHER, product_type="CreditCard"),
        ],
        "transactions": [
            transaction_row(
                transaction_id="TXN-001",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Transfer",
                transaction_status="Approved",
                transaction_date="2026-06-15 10:00:00",
                amount="150.00",
                amount_usd="150.00",
                channel="App",
                response_code="00",
            ),
            transaction_row(
                transaction_id="TXN-002",
                customer_id=OWNER,
                product_id="PROD-001",
                transaction_type="Payment",
                transaction_status="Declined",
                transaction_date="2026-06-16 11:30:00",
                amount="40.00",
                amount_usd="40.00",
                channel="App",
                response_code="51",
            ),
            # No response_code and no amount_usd: both gaps are real in the curated data and must
            # read back as absent facts rather than invented ones.
            transaction_row(
                transaction_id="TXN-003",
                customer_id=OWNER,
                product_id="PROD-002",
                transaction_type="Transfer",
                transaction_status="Pending",
                transaction_date="2026-06-17 09:15:00",
                amount="900.00",
                amount_usd="",
                channel="Web",
                response_code="",
            ),
            transaction_row(
                transaction_id="TXN-004",
                customer_id=OTHER,
                product_id="PROD-003",
                transaction_type="Payment",
                transaction_status="Declined",
                transaction_date="2026-06-16 08:00:00",
                amount="40.00",
                amount_usd="40.00",
                channel="App",
                response_code="51",
            ),
            transaction_row(
                transaction_id="TXN-005",
                customer_id=OTHER,
                product_id="PROD-003",
                transaction_type="Transfer",
                transaction_status="Approved",
                transaction_date="2026-06-17 12:00:00",
                amount="150.00",
                amount_usd="150.00",
                channel="App",
                response_code="00",
            ),
            transaction_row(
                transaction_id="TXN-006",
                customer_id=OTHER,
                product_id="PROD-003",
                transaction_type="Transfer",
                transaction_status="Approved",
                transaction_date="2026-06-15 10:00:00",
                amount="200.00",
                amount_usd="200.00",
                channel="Web",
                response_code="00",
            ),
        ],
    }


@pytest.fixture
def curated_database(data_root, banking_rows) -> Path:
    return run_pipeline(data_root(**banking_rows)).database_path


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 6, 18, 12, 0, tzinfo=UTC))


@pytest.fixture
def repository(curated_database) -> CuratedBankingRepository:
    return CuratedBankingRepository(curated_database)


@pytest.fixture
def audit_sink() -> InMemoryAuditSink:
    return InMemoryAuditSink()


@pytest.fixture
def sessions(clock) -> SessionStore:
    return SessionStore(ttl=SESSION_TTL, clock=clock)


@pytest.fixture
def service(repository, sessions, audit_sink, clock) -> BankingService:
    return BankingService(repository=repository, sessions=sessions, audit=audit_sink, clock=clock)


@pytest.fixture
def service_without_data(tmp_path, sessions, audit_sink, clock) -> BankingService:
    return BankingService(
        repository=CuratedBankingRepository(tmp_path / "absent" / "banking.duckdb"),
        sessions=sessions,
        audit=audit_sink,
        clock=clock,
    )


@pytest.fixture
def customer_session(service) -> str:
    return service.create_session(OWNER).session_id


@pytest.fixture
def other_session(service) -> str:
    return service.create_session(OTHER).session_id


# --- Incident workflow (Phase 3B) ----------------------------------------------------


@pytest.fixture
def incident_rows(banking_rows: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """The banking rows plus the states the workflow has to handle.

    Kept separate from `banking_rows` so the Phase 2 expectations about the curated tables stay
    exactly as they were.
    """
    rows = {key: list(value) for key, value in banking_rows.items()}
    rows["transactions"] += [
        transaction_row(
            transaction_id="TXN-007",
            customer_id=OWNER,
            product_id="PROD-001",
            transaction_type="Payment",
            transaction_status="Reversed",
            transaction_date="2026-06-16 15:45:00",
            process_date="2026-06-17",
            amount="40.00",
            amount_usd="40.00",
            channel="App",
            response_code="",
        ),
        # A second owned Payment on the same day: the customer reference alone stays ambiguous.
        transaction_row(
            transaction_id="TXN-008",
            customer_id=OWNER,
            product_id="PROD-001",
            transaction_type="Payment",
            transaction_status="Pending",
            transaction_date="2026-06-17 18:00:00",
            amount="40.00",
            amount_usd="40.00",
            channel="Web",
            response_code="",
        ),
    ]
    return rows


@pytest.fixture
def incident_database(data_root, incident_rows) -> Path:
    return run_pipeline(data_root(**incident_rows)).database_path


@pytest.fixture
def incident_service(incident_database, sessions, audit_sink, clock) -> BankingService:
    return BankingService(
        repository=CuratedBankingRepository(incident_database),
        sessions=sessions,
        audit=audit_sink,
        clock=clock,
    )


@pytest.fixture
def operational_store(tmp_path) -> OperationalStore:
    store = OperationalStore(tmp_path / "operational" / "app.db")
    store.initialize()
    return store


@pytest.fixture
def workflow(incident_service: BankingService, operational_store: OperationalStore, clock):
    return IncidentWorkflow(service=incident_service, store=operational_store, clock=clock)


@pytest.fixture
def incident_session(incident_service: BankingService) -> str:
    return incident_service.create_session(OWNER).session_id


@pytest.fixture
def other_incident_session(incident_service: BankingService) -> str:
    return incident_service.create_session(OTHER).session_id


def _client_for(service: BankingService, workflow: IncidentWorkflow) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: service
    app.dependency_overrides[get_incident_workflow] = lambda: workflow
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api_client(service) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: service
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api_client_without_data(service_without_data) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: service_without_data
    with TestClient(app) as client:
        yield client


@pytest.fixture
def workflow_client(incident_service, workflow) -> Iterator[TestClient]:
    yield from _client_for(incident_service, workflow)

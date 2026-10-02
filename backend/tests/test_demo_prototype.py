"""The Phase 5A demo surface: profile discovery, demo sessions, session-scoped context, timelines.

The prototype is only honest if every claim it makes is backed by the curated data, and only safe if
the catalogue leaks nothing. These tests therefore check two things beyond the status codes: that
each advertised profile really does contain the activity it advertises, and that no curated customer
identifier ever appears in a demo response.

The fixture gives each scenario its own customer, so the selection has four distinct profiles to
find. That is what the curated banking data produces, and a fixture where one customer satisfied
every scenario would test the dedup path instead of the happy path.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import customer_row, product_row, transaction_row
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_banking_service,
    get_demo_database_path,
    get_incident_workflow,
)
from app.banking.errors import Reason
from app.banking.repository import CuratedBankingRepository
from app.banking.service import BankingService
from app.data.pipeline import run_pipeline
from app.demo.profiles import list_demo_profiles
from app.main import create_app
from app.workflow.orchestrator import IncidentWorkflow
from app.workflow.storage import OperationalStore

DECLINED_OWNER = "CUST-001"
PENDING_OWNER = "CUST-002"
REVERSED_OWNER = "CUST-003"
AMBIGUOUS_OWNER = "CUST-004"
FOREIGN = "CUST-099"

DECLINED_TXN = "TXN-101"
PENDING_TXN = "TXN-201"
REVERSED_TXN = "TXN-301"
AMBIGUOUS_APPROVED_TXN = "TXN-401"
AMBIGUOUS_PENDING_TXN = "TXN-402"
FOREIGN_TXN = "TXN-901"


@pytest.fixture
def demo_database(data_root) -> Path:
    def movement(
        transaction_id: str,
        customer_id: str,
        *,
        transaction_type: str = "Payment",
        transaction_status: str = "Approved",
        amount: str = "40.00",
        channel: str = "App",
        response_code: str = "00",
    ) -> list[str]:
        return transaction_row(
            transaction_id=transaction_id,
            customer_id=customer_id,
            product_id=f"PROD-{customer_id[-3:]}",
            transaction_type=transaction_type,
            transaction_status=transaction_status,
            amount=amount,
            amount_usd=amount,
            channel=channel,
            response_code=response_code,
        )

    customers = [
        customer_row(customer_id=customer)
        for customer in (DECLINED_OWNER, PENDING_OWNER, REVERSED_OWNER, AMBIGUOUS_OWNER, FOREIGN)
    ]
    products = [
        product_row(
            product_id=f"PROD-{customer[-3:]}",
            customer_id=customer,
            product_type="Checking",
            current_balance=f"{100 + index}.50",
        )
        for index, customer in enumerate(
            (DECLINED_OWNER, PENDING_OWNER, REVERSED_OWNER, AMBIGUOUS_OWNER, FOREIGN)
        )
    ]
    transactions = [
        # One declined movement, so a resolved incident has something to resolve.
        movement(DECLINED_TXN, DECLINED_OWNER, transaction_status="Declined", response_code="51"),
        movement(
            "TXN-102",
            DECLINED_OWNER,
            transaction_type="Transfer",
            amount="150.00",
            channel="Web",
        ),
        # One movement with no response code, because a missing fact must stay missing.
        movement(
            PENDING_TXN,
            PENDING_OWNER,
            transaction_type="Transfer",
            transaction_status="Pending",
            amount="900.00",
            channel="Web",
            response_code="",
        ),
        movement(
            REVERSED_TXN,
            REVERSED_OWNER,
            transaction_status="Reversed",
            amount="55.00",
            response_code="",
        ),
        # Two identical Payments: the customer reference alone cannot single one out.
        movement(AMBIGUOUS_APPROVED_TXN, AMBIGUOUS_OWNER, amount="25.00"),
        movement(AMBIGUOUS_PENDING_TXN, AMBIGUOUS_OWNER, amount="25.00", response_code=""),
        # A second declined movement that belongs to nobody in the catalogue.
        movement(FOREIGN_TXN, FOREIGN, transaction_status="Declined", response_code="51"),
    ]
    return run_pipeline(
        data_root(customers=customers, products=products, transactions=transactions)
    ).database_path


@pytest.fixture
def demo_service(demo_database, sessions, audit_sink, clock) -> BankingService:
    return BankingService(
        repository=CuratedBankingRepository(demo_database),
        sessions=sessions,
        audit=audit_sink,
        clock=clock,
    )


@pytest.fixture
def demo_store(tmp_path) -> OperationalStore:
    store = OperationalStore(tmp_path / "operational" / "app.db")
    store.initialize()
    return store


@pytest.fixture
def demo_workflow(demo_service, demo_store, clock) -> IncidentWorkflow:
    return IncidentWorkflow(service=demo_service, store=demo_store, clock=clock)


@pytest.fixture
def demo_client(demo_service, demo_workflow, demo_database) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: demo_service
    app.dependency_overrides[get_incident_workflow] = lambda: demo_workflow
    app.dependency_overrides[get_demo_database_path] = lambda: demo_database
    with TestClient(app) as client:
        yield client


def _profiles(client: TestClient) -> list[dict]:
    response = client.get("/api/demo/profiles")
    assert response.status_code == 200, response.text
    return response.json()["profiles"]


def _open_demo_session(client: TestClient, profile_id: str) -> str:
    response = client.post("/api/demo/sessions", json={"profile_id": profile_id})
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def _transactions(client: TestClient, session_id: str, params: dict | None = None) -> list[dict]:
    response = client.get(
        "/api/transactions", params=params or {}, headers={"X-Session-Id": session_id}
    )
    assert response.status_code == 200, response.text
    return response.json()["transactions"]


# --- Catalogue ---------------------------------------------------------------------------


def test_catalogue_is_readable_before_any_session_exists(demo_client) -> None:
    profiles = _profiles(demo_client)

    assert [profile["profile_id"] for profile in profiles] == [
        "declined",
        "pending",
        "reversed",
        "ambiguous",
    ]
    assert [profile["display_name"] for profile in profiles] == [
        "Demo Customer A",
        "Demo Customer B",
        "Demo Customer C",
        "Demo Customer D",
    ]


def test_catalogue_is_deterministic(demo_client) -> None:
    assert _profiles(demo_client) == _profiles(demo_client)


def test_catalogue_never_reveals_a_curated_customer(demo_client) -> None:
    body = demo_client.get("/api/demo/profiles").text

    for forbidden in (
        DECLINED_OWNER,
        PENDING_OWNER,
        REVERSED_OWNER,
        AMBIGUOUS_OWNER,
        FOREIGN,
        "PROD-001",
        DECLINED_TXN,
    ):
        assert forbidden not in body


def test_each_profile_stands_for_a_different_customer(demo_service, demo_client) -> None:
    # Proven through behaviour rather than internals: no two profiles may read the same account.
    seen = []
    for profile_id in ("declined", "pending", "reversed", "ambiguous"):
        session_id = _open_demo_session(demo_client, profile_id)
        customer_id = demo_service.sessions.resolve(session_id).customer_id
        assert customer_id not in seen
        seen.append(customer_id)


def test_each_advertised_status_really_exists_for_its_profile(demo_client) -> None:
    for profile in _profiles(demo_client):
        if profile["highlight_status"] is None:
            continue
        session_id = _open_demo_session(demo_client, profile["profile_id"])
        rows = _transactions(demo_client, session_id)

        statuses = [row["transaction_status"] for row in rows]
        assert profile["highlight_status"] in statuses
        assert statuses.count(profile["highlight_status"]) == profile["highlight_count"]
        assert len(rows) == profile["transaction_count"]


def test_the_ambiguous_profile_advertises_a_filter_that_cannot_resolve_to_one(demo_client) -> None:
    profile = next(p for p in _profiles(demo_client) if p["profile_id"] == "ambiguous")
    prefill = profile["prefill_filters"]
    assert prefill == {"transaction_type": "Payment", "currency": "USD"}

    session_id = _open_demo_session(demo_client, "ambiguous")
    matching = _transactions(demo_client, session_id, prefill)

    # The whole point of the profile: the filter the frontend is offered matches more than one
    # movement, so the workflow has to clarify rather than guess.
    assert {row["transaction_id"] for row in matching} == {
        AMBIGUOUS_APPROVED_TXN,
        AMBIGUOUS_PENDING_TXN,
    }


def test_headlines_never_claim_a_transaction_type(demo_client) -> None:
    # The selection queries do not read transaction_type, so the copy must not mention one.
    banned = ("transfer", "payment", "withdrawal", "deposit")
    for profile in _profiles(demo_client):
        assert not any(word in profile["headline"].lower() for word in banned)


# --- Demo sessions ----------------------------------------------------------------------


def test_demo_session_opens_for_the_selected_profile(demo_client) -> None:
    response = demo_client.post("/api/demo/sessions", json={"profile_id": "declined"})

    assert response.status_code == 201
    body = response.json()
    assert body["profile_id"] == "declined"
    assert body["display_name"] == "Demo Customer A"
    assert len(body["session_id"]) >= 32
    assert body["expires_at"] > body["issued_at"]


def test_demo_session_response_carries_no_customer_identifier(demo_client) -> None:
    body = demo_client.post("/api/demo/sessions", json={"profile_id": "reversed"}).text

    assert DECLINED_OWNER not in body
    assert "customer_id" not in body


def test_demo_session_works_on_every_banking_read(demo_client) -> None:
    session_id = _open_demo_session(demo_client, "pending")

    context = demo_client.get("/api/customer/context", headers={"X-Session-Id": session_id})
    rows = _transactions(demo_client, session_id)

    assert context.status_code == 200, context.text
    assert rows, "the pending profile must own at least one movement"
    assert any(row["transaction_status"] == "Pending" for row in rows)


def test_unknown_demo_profile_is_a_request_error(demo_client) -> None:
    response = demo_client.post("/api/demo/sessions", json={"profile_id": "does-not-exist"})

    assert response.status_code == 400
    assert response.json()["error"] == Reason.INVALID_REQUEST.value


def test_demo_session_request_accepts_nothing_beyond_a_profile_id(demo_client) -> None:
    response = demo_client.post(
        "/api/demo/sessions", json={"profile_id": "declined", "customer_id": FOREIGN}
    )

    assert response.status_code == 422


def test_a_profile_never_falls_back_to_a_customer_the_caller_named(demo_client) -> None:
    # FOREIGN owns the only other declined movement. Asking for the declined profile must land on
    # the profile's own selection, not on whichever customer the search happened to rank first.
    session_id = _open_demo_session(demo_client, "declined")
    rows = _transactions(demo_client, session_id)

    assert {row["customer_id"] for row in rows} == {DECLINED_OWNER}


# --- Session-scoped context -------------------------------------------------------------


def test_customer_context_requires_a_session(demo_client) -> None:
    response = demo_client.get("/api/customer/context")

    assert response.status_code == 401
    assert response.json()["error"] == Reason.INVALID_SESSION.value


def test_customer_context_rejects_a_customer_query_parameter(demo_client) -> None:
    # Rejected rather than ignored, so a caller can never believe it narrowed the read.
    session_id = _open_demo_session(demo_client, "declined")

    response = demo_client.get(
        "/api/customer/context",
        params={"customer_id": FOREIGN},
        headers={"X-Session-Id": session_id},
    )

    assert response.status_code == 400
    assert response.json()["error"] == Reason.INVALID_REQUEST.value


def test_customer_context_reads_the_authenticated_customer(demo_client, demo_service) -> None:
    session_id = demo_service.create_session(FOREIGN).session_id

    response = demo_client.get("/api/customer/context", headers={"X-Session-Id": session_id})

    assert response.status_code == 200
    assert response.json()["customer"]["customer_id"] == FOREIGN


# --- Incident timelines -----------------------------------------------------------------


def _raise_incident(client: TestClient, session_id: str, transaction_id: str) -> str:
    response = client.post(
        "/api/incidents",
        json={"transaction_id": transaction_id},
        headers={"X-Session-Id": session_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["incident_id"]


def test_owner_reads_the_steps_of_their_own_incident(demo_client) -> None:
    session_id = _open_demo_session(demo_client, "pending")
    incident_id = _raise_incident(demo_client, session_id, PENDING_TXN)

    response = demo_client.get(
        f"/api/incidents/{incident_id}/events", headers={"X-Session-Id": session_id}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["incident_id"] == incident_id
    assert [event["event_type"] for event in body["events"]] == [
        "incident_created",
        "transaction_verified",
        "policy_evaluated",
        "support_case_creation_attempted",
        "support_case_created",
        "support_case_verified",
        "workflow_escalated",
    ]


def test_timeline_requires_a_session(demo_client) -> None:
    session_id = _open_demo_session(demo_client, "pending")
    incident_id = _raise_incident(demo_client, session_id, PENDING_TXN)

    response = demo_client.get(f"/api/incidents/{incident_id}/events")

    assert response.status_code == 401
    assert response.json()["error"] == Reason.INVALID_SESSION.value


def test_timeline_of_another_customer_is_indistinguishable_from_an_absent_one(
    demo_client, demo_service
) -> None:
    session_id = _open_demo_session(demo_client, "pending")
    incident_id = _raise_incident(demo_client, session_id, PENDING_TXN)
    headers = {"X-Session-Id": demo_service.create_session(FOREIGN).session_id}

    foreign = demo_client.get(f"/api/incidents/{incident_id}/events", headers=headers)
    absent = demo_client.get("/api/incidents/INC-nonexistent/events", headers=headers)

    assert foreign.status_code == absent.status_code == 404
    assert foreign.json() == absent.json()
    assert foreign.json()["error"] == Reason.INCIDENT_NOT_FOUND.value


def test_timeline_details_carry_no_customer_or_personal_data(demo_client) -> None:
    session_id = _open_demo_session(demo_client, "pending")
    incident_id = _raise_incident(demo_client, session_id, PENDING_TXN)

    body = demo_client.get(
        f"/api/incidents/{incident_id}/events", headers={"X-Session-Id": session_id}
    ).text

    assert PENDING_OWNER not in body
    assert "Samuel" not in body
    assert "G8637940" not in body


def test_reading_a_timeline_twice_changes_nothing(demo_client, demo_store) -> None:
    session_id = _open_demo_session(demo_client, "pending")
    incident_id = _raise_incident(demo_client, session_id, PENDING_TXN)
    before = demo_store.get_incident(incident_id)

    first = demo_client.get(
        f"/api/incidents/{incident_id}/events", headers={"X-Session-Id": session_id}
    )
    second = demo_client.get(
        f"/api/incidents/{incident_id}/events", headers={"X-Session-Id": session_id}
    )

    assert first.json() == second.json()
    assert demo_store.get_incident(incident_id) == before
    assert len(demo_store.events_for(incident_id)) == 7


# --- Catalogue edge cases ---------------------------------------------------------------


def test_catalogue_skips_a_scenario_with_nothing_to_select(data_root, tmp_path) -> None:
    # Approved-only data still produces a provable ambiguity, but no declined, pending or reversed
    # movement, so those scenarios are dropped instead of being padded with a placeholder.
    quiet = run_pipeline(
        data_root(
            customers=[customer_row()],
            products=[product_row()],
            transactions=[
                transaction_row(transaction_id="TXN-001"),
                transaction_row(transaction_id="TXN-002", amount="200.00", amount_usd="200.00"),
            ],
        )
    ).database_path

    profiles = list_demo_profiles(quiet)

    assert [profile.profile_id for profile in profiles] == ["ambiguous"]
    assert list_demo_profiles(quiet) == profiles


def test_catalogue_reports_a_missing_database_as_data_unavailable(tmp_path) -> None:
    with pytest.raises(Exception) as raised:
        list_demo_profiles(tmp_path / "absent" / "banking.duckdb")

    error = raised.value
    assert error.reason is Reason.DATA_UNAVAILABLE
    assert error.message == "Banking data is unavailable."

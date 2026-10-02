"""The minimum incident endpoint: thin, structured and closed to caller-supplied verdicts.

Every test asserts through the HTTP surface, because that is where the security contract has to
hold for a future AI/ML caller: the request cannot carry a status, an outcome, an identity or an
unrecognized field, and the response is the workflow's structured result.
"""

import pytest
from conftest import ABSENT_CUSTOMER, OWNER
from fastapi.testclient import TestClient

from app.api.dependencies import get_banking_service, get_incident_workflow
from app.main import create_app
from app.workflow.orchestrator import IncidentWorkflow

DECLINED = "TXN-002"
PENDING = "TXN-003"
APPROVED = "TXN-001"
ABSENT_TRANSACTION = "TXN-999"
FOREIGN_TRANSACTION = "TXN-004"


def _post(client, session_id, body) -> dict:
    headers = {} if session_id is None else {"X-Session-Id": session_id}
    response = client.post("/api/incidents", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- Structured results ------------------------------------------------------------------


def test_resolvable_incident_returns_its_verified_record(workflow_client, incident_session) -> None:
    body = _post(workflow_client, incident_session, {"transaction_id": DECLINED})

    assert body["status"] == "completed"
    assert body["policy_decision"]["outcome"] == "RESOLVE"
    assert body["policy_decision"]["policy_rule"] == "F_DECLINED"
    assert body["verified_transaction"]["transaction_status"] == "Declined"
    assert body["support_case"] is None
    assert body["handoff"] is None
    assert body["failure"] is None


def test_escalated_incident_returns_a_case_and_handoff(workflow_client, incident_session) -> None:
    body = _post(workflow_client, incident_session, {"transaction_id": PENDING})

    assert body["policy_decision"]["outcome"] == "ESCALATE"
    assert body["support_case"]["status"] == "open"
    assert body["support_case"]["recommended_route"] == "PAYMENTS_OPERATIONS"
    assert body["support_case"]["incident_id"] == body["incident_id"]
    assert body["handoff"]["case_id"] == body["support_case"]["case_id"]
    assert body["handoff"]["verified_facts"]


def test_candidate_search_returns_a_clarification(workflow_client, incident_session) -> None:
    body = _post(
        workflow_client,
        incident_session,
        {"filters": {"transaction_type": "Payment"}},
    )

    assert body["policy_decision"]["outcome"] == "CLARIFY"
    assert body["clarification"]["reason"] == "multiple_candidate_transactions"
    assert [candidate["transaction_id"] for candidate in body["clarification"]["candidates"]] == [
        "TXN-008",
        "TXN-007",
        DECLINED,
    ]
    assert body["verified_transaction"] is None


def test_out_of_scope_incident_abstains(workflow_client, incident_session) -> None:
    body = _post(workflow_client, incident_session, {"transaction_id": DECLINED, "in_scope": False})

    assert body["policy_decision"]["outcome"] == "ABSTAIN"
    assert body["policy_decision"]["reason_code"] == "out_of_scope"
    assert body["support_case"] is None


# --- Session handling --------------------------------------------------------------------


def test_missing_session_abstains(workflow_client, audit_sink) -> None:
    body = _post(workflow_client, None, {"transaction_id": DECLINED})

    assert body["policy_decision"]["outcome"] == "ABSTAIN"
    assert body["policy_decision"]["reason_code"] == "invalid_session"
    assert body["verified_transaction"] is None
    assert audit_sink.recent(limit=10) == []


@pytest.mark.parametrize("session_id", ["", "   ", "forged-session"])
def test_unusable_session_abstains(workflow_client, session_id) -> None:
    body = _post(workflow_client, session_id, {"transaction_id": DECLINED})

    assert body["policy_decision"]["outcome"] == "ABSTAIN"
    assert body["policy_decision"]["policy_rule"] == "A_INVALID_UNAUTHORIZED_WORKFLOW"


def test_foreign_transaction_looks_absent(workflow_client, incident_session) -> None:
    foreign = _post(workflow_client, incident_session, {"transaction_id": FOREIGN_TRANSACTION})
    absent = _post(workflow_client, incident_session, {"transaction_id": ABSENT_TRANSACTION})

    assert foreign["policy_decision"] == absent["policy_decision"]
    assert foreign["policy_decision"]["outcome"] == "CLARIFY"


def test_each_call_is_a_new_incident(workflow_client, incident_session) -> None:
    first = _post(workflow_client, incident_session, {"transaction_id": DECLINED})
    second = _post(workflow_client, incident_session, {"transaction_id": DECLINED})

    assert first["incident_id"] != second["incident_id"]


# --- Request rejection -------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"transaction_id": DECLINED, "filters": {"transaction_type": "Payment"}},
        {"transaction_id": ""},
        {"transaction_id": "   "},
        {"filters": {"transaction_type": "Payment"}, "approved_with_unresolved_issue": "maybe"},
        {"transaction_id": DECLINED, "in_scope": "yes"},
    ],
)
def test_ambiguous_or_malformed_input_is_rejected(workflow_client, incident_session, body) -> None:
    response = workflow_client.post(
        "/api/incidents", json=body, headers={"X-Session-Id": incident_session}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"transaction_status": "Approved"},
        {"transaction_id": DECLINED, "outcome": "resolve"},
        {"transaction_id": DECLINED, "policy_rule": "F_DECLINED"},
        {"transaction_id": DECLINED, "customer_id": ABSENT_CUSTOMER},
        {"transaction_id": DECLINED, "description": "customer says the transfer failed"},
        {"transaction_id": DECLINED, "message": "why was I charged?"},
    ],
)
def test_caller_supplied_verdicts_and_prose_are_refused(
    workflow_client, incident_session, override
) -> None:
    # No path to assert a status, pick an outcome, name a rule or identify a customer, and no
    # natural-language field at all.
    response = workflow_client.post(
        "/api/incidents", json=override, headers={"X-Session-Id": incident_session}
    )

    assert response.status_code == 422


def test_out_of_domain_filter_value_is_rejected(workflow_client, incident_session) -> None:
    response = workflow_client.post(
        "/api/incidents",
        json={"filters": {"transaction_status": "Escheated"}},
        headers={"X-Session-Id": incident_session},
    )

    assert response.status_code == 400


def test_unknown_filter_key_is_rejected(workflow_client, incident_session) -> None:
    # A typo like "transaction_staus" must not be silently dropped: that would widen the search
    # and trace an incident to a transaction the caller never named.
    response = workflow_client.post(
        "/api/incidents",
        json={"filters": {"transaction_staus": "Declined"}},
        headers={"X-Session-Id": incident_session},
    )

    assert response.status_code == 422


def test_malformed_body_is_rejected(workflow_client, incident_session) -> None:
    response = workflow_client.post(
        "/api/incidents",
        content="not json",
        headers={"X-Session-Id": incident_session},
    )

    assert response.status_code == 422


# --- Existing surfaces are untouched ------------------------------------------------------


@pytest.fixture
def data_less_client(service_without_data, operational_store, clock):
    """A client whose curated database is absent, so the workflow reads a failed Banking Core."""

    workflow = IncidentWorkflow(service=service_without_data, store=operational_store, clock=clock)
    session_id = service_without_data.create_session(OWNER).session_id
    app = create_app()
    app.dependency_overrides[get_banking_service] = lambda: service_without_data
    app.dependency_overrides[get_incident_workflow] = lambda: workflow
    with TestClient(app) as client:
        yield client, session_id


def test_banking_endpoints_keep_their_own_semantics(api_client, customer_session) -> None:
    headers = {"X-Session-Id": customer_session}

    response = api_client.get(f"/api/transactions/{DECLINED}", headers=headers)

    assert response.status_code == 200
    assert response.json()["transaction_status"] == "Declined"

    missing = api_client.get("/api/transactions/does-not-exist", headers=headers)
    assert missing.status_code == 404

    foreign = api_client.get("/api/transactions/TXN-004", headers=headers)
    assert foreign.status_code == 404

    unauthenticated = api_client.get(f"/api/transactions/{DECLINED}")
    assert unauthenticated.status_code == 401


def test_workflow_endpoint_survives_a_banking_data_failure(data_less_client) -> None:
    # The workflow reads the same curated database the banking routes do; when it is unavailable the
    # workflow escalates rather than pretending the transaction is absent.
    client, session_id = data_less_client
    response = client.post(
        "/api/incidents",
        json={"transaction_id": DECLINED},
        headers={"X-Session-Id": session_id},
    )

    assert response.status_code == 200
    assert response.json()["policy_decision"]["reason_code"] == "tool_failure_exhausted"
    assert response.json()["support_case"] is not None
    assert response.json()["verified_transaction"] is None


def test_an_unbounded_search_still_requires_a_clarification(
    workflow_client, incident_session
) -> None:
    # No filter at all is a legitimate request for everything the customer owns; the workflow
    # returns the candidates instead of choosing one.
    body = _post(workflow_client, incident_session, {"filters": {}})

    assert body["policy_decision"]["outcome"] == "CLARIFY"
    assert len(body["clarification"]["candidates"]) > 1
    assert body["verified_transaction"] is None


def test_owner_never_sees_another_customers_rows(workflow_client, other_incident_session) -> None:
    body = _post(
        workflow_client,
        other_incident_session,
        {"filters": {"transaction_type": "Transfer"}},
    )

    offered = [candidate["transaction_id"] for candidate in body["clarification"]["candidates"]]
    assert offered == ["TXN-005", "TXN-006"]
    assert all(
        candidate.get("customer_id") is None for candidate in body["clarification"]["candidates"]
    )
    assert OWNER not in body["incident_id"]

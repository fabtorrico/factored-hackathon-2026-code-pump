"""The read-only Human Agent Workspace.

These tests assert through the HTTP surface, because the contract is what a browser (and a future
agent UI) sees: a separate demo agent session gates the reads, the queue is built only from
persisted support cases, the detail replays the persisted handoff, and nothing exposes a customer
identity or an unverified claim.
"""

import pytest
from conftest import OWNER
from fastapi.testclient import TestClient

from app.workflow.models import CaseStatus, SupportCase, SupportRoute, new_case_id

PENDING = "TXN-003"
DECLINED = "TXN-002"
APPROVED = "TXN-001"


def _open_agent_session(agent_client: TestClient) -> str:
    response = agent_client.post("/api/agent/sessions")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["display_name"]
    return body["agent_session_id"]


def _escalate(workflow_client: TestClient, session_id: str, transaction_id: str = PENDING) -> dict:
    response = workflow_client.post(
        "/api/incidents",
        json={"transaction_id": transaction_id},
        headers={"X-Session-Id": session_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["support_case"] is not None
    return body


def _agent_headers(agent_session_id: str) -> dict[str, str]:
    return {"X-Agent-Session-Id": agent_session_id}


def test_agent_reads_require_their_own_session(
    agent_client, workflow_client, incident_session
) -> None:
    _escalate(workflow_client, incident_session)
    agent_session = _open_agent_session(agent_client)

    assert agent_client.get("/api/agent/cases").status_code == 401
    # A valid customer session is not an agent credential.
    wrong = agent_client.get("/api/agent/cases", headers={"X-Agent-Session-Id": incident_session})
    assert wrong.status_code == 401
    assert wrong.json()["error"] == "invalid_session"

    allowed = agent_client.get("/api/agent/cases", headers=_agent_headers(agent_session))
    assert allowed.status_code == 200


def test_queue_is_built_from_persisted_cases_only(
    agent_client, workflow_client, incident_session
) -> None:
    # A resolved incident creates no case, so it must not appear in the queue.
    resolved = workflow_client.post(
        "/api/incidents",
        json={"transaction_id": DECLINED},
        headers={"X-Session-Id": incident_session},
    )
    assert resolved.json()["support_case"] is None
    escalated = _escalate(workflow_client, incident_session)
    agent_session = _open_agent_session(agent_client)

    body = agent_client.get("/api/agent/cases", headers=_agent_headers(agent_session)).json()

    assert len(body["cases"]) == 1
    case = body["cases"][0]
    assert case["case_id"] == escalated["support_case"]["case_id"]
    assert case["incident_id"] == escalated["incident_id"]
    assert case["status"] == "open"
    assert case["workflow_status"] == "completed"
    assert case["outcome"] == "ESCALATE"
    assert case["reason_code"] == "pending_status"
    assert case["recommended_route"] == "PAYMENTS_OPERATIONS"
    assert case["has_handoff"] is True
    assert case["unresolved_count"] == 1
    assert case["movement"]["transaction_status"] == "Pending"
    assert case["movement"]["transaction_type"] == "Transfer"


def test_queue_never_carries_a_customer_identity(
    agent_client, workflow_client, incident_session
) -> None:
    _escalate(workflow_client, incident_session)
    agent_session = _open_agent_session(agent_client)

    body = agent_client.get("/api/agent/cases", headers=_agent_headers(agent_session))

    assert OWNER not in body.text
    assert "customer_id" not in body.text
    assert "Samuel" not in body.text


def test_detail_replays_the_persisted_handoff_and_timeline(
    agent_client, workflow_client, incident_session
) -> None:
    escalated = _escalate(workflow_client, incident_session)
    agent_session = _open_agent_session(agent_client)
    case_id = escalated["support_case"]["case_id"]

    body = agent_client.get(
        f"/api/agent/cases/{case_id}", headers=_agent_headers(agent_session)
    ).json()

    handoff = body["handoff"]
    assert handoff is not None
    assert handoff["case_id"] == case_id
    assert handoff["incident_id"] == escalated["incident_id"]
    assert handoff["customer_request"]["transaction_reference"] == PENDING
    assert handoff["unresolved_questions"] == ["final_settlement_state_unavailable"]
    assert body["case"]["has_handoff"] is True
    event_types = [event["event_type"] for event in body["events"]]
    assert event_types == [
        "incident_created",
        "transaction_verified",
        "policy_evaluated",
        "support_case_creation_attempted",
        "support_case_created",
        "support_case_verified",
        "workflow_escalated",
    ]


def test_unknown_case_is_not_found(agent_client) -> None:
    agent_session = _open_agent_session(agent_client)

    response = agent_client.get(
        f"/api/agent/cases/{new_case_id()}", headers=_agent_headers(agent_session)
    )

    assert response.status_code == 404
    assert response.json()["error"] == "case_not_found"


def test_a_case_without_a_stored_handoff_is_reported_honestly(
    agent_client, operational_store, clock
) -> None:
    # Simulates a case written before handoffs were persisted, or one whose handoff was not stored.
    from app.policy import PolicyOutcome, PolicyReasonCode, PolicyRule
    from app.workflow.models import Incident, WorkflowStatus

    incident_id = new_case_id()
    operational_store.save_incident(
        Incident(
            incident_id=incident_id,
            customer_id=OWNER,
            created_at=clock.now,
            status=WorkflowStatus.COMPLETED,
            outcome=PolicyOutcome.ESCALATE,
            reason_code=PolicyReasonCode.PENDING_STATUS,
            policy_rule=PolicyRule.G_PENDING,
            transaction_id=PENDING,
        )
    )
    case = SupportCase(
        case_id=new_case_id(),
        incident_id=incident_id,
        status=CaseStatus.OPEN,
        recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
        created_at=clock.now,
    )
    operational_store.create_support_case(case)
    agent_session = _open_agent_session(agent_client)

    body = agent_client.get(
        f"/api/agent/cases/{case.case_id}", headers=_agent_headers(agent_session)
    ).json()

    assert body["case"]["has_handoff"] is False
    assert body["case"]["movement"]["transaction_reference"] == PENDING
    assert body["case"]["movement"]["transaction_status"] is None
    assert body["handoff"] is None
    assert body["events"] == []


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_the_agent_workspace_is_read_only(agent_client, method) -> None:
    agent_session = _open_agent_session(agent_client)
    path = f"/api/agent/cases/{new_case_id()}"

    response = getattr(agent_client, method)(path, headers=_agent_headers(agent_session))

    assert response.status_code == 405

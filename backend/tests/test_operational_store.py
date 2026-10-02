"""Operational store behavior: deterministic schema, UTC round trips and verified writes.

The store is the only place application-generated state is persisted. These tests pin the
properties the workflow relies on: idempotent initialization, timezone-aware timestamps, event
ordering, and a foreign key that makes an escalation impossible without an incident.
"""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest
from conftest import OWNER

from app.policy import PolicyDecision, PolicyOutcome, PolicyReasonCode, PolicyRule
from app.workflow.handoff import build_handoff
from app.workflow.models import (
    CaseStatus,
    Handoff,
    IdentificationMode,
    Incident,
    IncidentSummary,
    SupportCase,
    SupportRoute,
    WorkflowAction,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
    new_case_id,
    new_incident_id,
)
from app.workflow.storage import OperationalStore, OperationalStoreError


def _incident(incident_id: str, created_at: datetime) -> Incident:
    return Incident(
        incident_id=incident_id,
        customer_id=OWNER,
        created_at=created_at,
        status=WorkflowStatus.OPEN,
        outcome=PolicyOutcome.ESCALATE,
        reason_code=PolicyReasonCode.PENDING_STATUS,
        policy_rule=PolicyRule.G_PENDING,
        transaction_id="TXN-003",
    )


@pytest.fixture
def incident_id() -> str:
    return new_incident_id()


def test_initialization_is_idempotent(operational_store, incident_id, clock) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))
    operational_store.initialize()
    operational_store.initialize()

    assert operational_store.get_incident(incident_id) is not None
    with sqlite3.connect(operational_store.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"incidents", "support_cases", "workflow_events", "handoffs"} <= tables


def test_initialization_creates_the_missing_directory(tmp_path) -> None:
    store = OperationalStore(tmp_path / "nested" / "operational" / "app.db")

    store.initialize()

    assert store.database_path.exists()


def test_unknown_incident_is_not_an_error(operational_store) -> None:
    assert operational_store.get_incident(new_incident_id()) is None
    assert operational_store.get_support_case(new_case_id()) is None
    assert operational_store.events_for(new_incident_id()) == []


def test_incident_round_trips_every_field(operational_store, incident_id, clock) -> None:
    incident = _incident(incident_id, clock.now)
    operational_store.save_incident(incident)

    assert operational_store.get_incident(incident_id) == incident


def test_timestamps_are_stored_and_returned_in_utc(operational_store, incident_id, clock) -> None:
    # A non-UTC input must come back as the same instant in UTC, never as a naive timestamp.
    created_at = datetime(2026, 6, 18, 9, 30, tzinfo=timezone(timedelta(hours=3)))
    operational_store.save_incident(_incident(incident_id, created_at))

    stored = operational_store.get_incident(incident_id)

    assert stored.created_at == created_at
    assert stored.created_at.tzinfo is UTC
    assert stored.created_at.utcoffset() == timedelta(0)


def test_terminal_status_is_written_after_verification(
    operational_store, incident_id, clock
) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))

    operational_store.finalize_incident(incident_id, WorkflowStatus.COMPLETED)

    assert operational_store.get_incident(incident_id).status is WorkflowStatus.COMPLETED


def test_finalizing_an_unknown_incident_changes_nothing(operational_store, clock) -> None:
    unknown = new_incident_id()
    operational_store.save_incident(_incident(unknown, clock.now))

    operational_store.finalize_incident(new_incident_id(), WorkflowStatus.FAILED)

    assert operational_store.get_incident(unknown).status is WorkflowStatus.OPEN


def test_support_case_round_trips_and_can_be_read_back(
    operational_store, incident_id, clock
) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))
    case = SupportCase(
        case_id=new_case_id(),
        incident_id=incident_id,
        status=CaseStatus.OPEN,
        recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
        created_at=clock.now,
    )

    operational_store.create_support_case(case)

    # Act then verify: the same row read back is the only proof of creation.
    assert operational_store.get_support_case(case.case_id) == case


def test_support_case_requires_an_existing_incident(operational_store) -> None:
    case = SupportCase(
        case_id=new_case_id(),
        incident_id=new_incident_id(),
        status=CaseStatus.OPEN,
        recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
        created_at=datetime(2026, 6, 18, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(OperationalStoreError):
        operational_store.create_support_case(case)

    assert operational_store.get_support_case(case.case_id) is None


def _case(incident_id: str, created_at: datetime, case_id: str | None = None) -> SupportCase:
    return SupportCase(
        case_id=case_id or new_case_id(),
        incident_id=incident_id,
        status=CaseStatus.OPEN,
        recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
        created_at=created_at,
    )


def _handoff(case: SupportCase) -> Handoff:
    return build_handoff(
        incident_id=case.incident_id,
        case_id=case.case_id,
        request=IncidentSummary(
            identification_mode=IdentificationMode.EXACT,
            transaction_reference="TXN-003",
            in_scope=True,
            approved_with_unresolved_issue=False,
        ),
        decision=PolicyDecision(
            outcome=PolicyOutcome.ESCALATE,
            reason_code=PolicyReasonCode.PENDING_STATUS,
            policy_rule=PolicyRule.G_PENDING,
        ),
        session_valid=True,
        record=None,
        actions=(WorkflowAction.SESSION_VALIDATED, WorkflowAction.POLICY_EVALUATED),
    )


def test_support_cases_are_listed_newest_first(operational_store, incident_id, clock) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))
    older = _case(incident_id, clock.now - timedelta(minutes=5))
    newer = _case(incident_id, clock.now)
    operational_store.create_support_case(older)
    operational_store.create_support_case(newer)

    listed = operational_store.list_support_cases()

    assert [case.case_id for case in listed] == [newer.case_id, older.case_id]


def test_handoff_round_trips_through_json(operational_store, incident_id, clock) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))
    case = _case(incident_id, clock.now)
    operational_store.create_support_case(case)
    handoff = _handoff(case)

    operational_store.save_handoff(handoff, clock.now)

    assert operational_store.get_handoff(case.case_id) == handoff


def test_unknown_handoff_is_not_an_error(operational_store) -> None:
    assert operational_store.get_handoff(new_case_id()) is None


def test_handoff_requires_an_existing_case(operational_store, incident_id, clock) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))
    orphan = _handoff(_case(incident_id, clock.now))

    with pytest.raises(OperationalStoreError):
        operational_store.save_handoff(orphan, clock.now)

    assert operational_store.get_handoff(orphan.case_id) is None


def test_duplicate_incident_identifier_is_refused(operational_store, incident_id, clock) -> None:
    operational_store.save_incident(_incident(incident_id, clock.now))

    with pytest.raises(sqlite3.IntegrityError):
        operational_store.save_incident(_incident(incident_id, clock.now))


def test_events_are_kept_in_written_order(operational_store, incident_id, clock) -> None:
    types = [
        WorkflowEventType.INCIDENT_CREATED,
        WorkflowEventType.POLICY_EVALUATED,
        WorkflowEventType.SUPPORT_CASE_CREATION_ATTEMPTED,
        WorkflowEventType.SUPPORT_CASE_VERIFIED,
        WorkflowEventType.WORKFLOW_ESCALATED,
    ]
    for offset, event_type in enumerate(types):
        operational_store.record_event(
            WorkflowEvent(
                incident_id=incident_id,
                occurred_at=clock.now + timedelta(seconds=offset),
                event_type=event_type,
                detail={"position": str(offset)},
            )
        )

    events = operational_store.events_for(incident_id)

    assert [event.event_type for event in events] == types
    assert [event.detail["position"] for event in events] == ["0", "1", "2", "3", "4"]
    assert all(event.occurred_at.tzinfo is UTC for event in events)


def test_events_are_scoped_to_one_incident(operational_store, incident_id, clock) -> None:
    other = new_incident_id()
    for current in (incident_id, other, incident_id):
        operational_store.record_event(
            WorkflowEvent(
                incident_id=current,
                occurred_at=clock.now,
                event_type=WorkflowEventType.INCIDENT_CREATED,
            )
        )

    assert len(operational_store.events_for(incident_id)) == 2
    assert len(operational_store.events_for(other)) == 1


def test_event_detail_is_valid_json_and_survives_the_round_trip(
    operational_store, incident_id, clock
) -> None:
    operational_store.record_event(
        WorkflowEvent(
            incident_id=incident_id,
            occurred_at=clock.now,
            event_type=WorkflowEventType.POLICY_EVALUATED,
            detail={"outcome": "escalate", "policy_rule": "G_PENDING", "in_scope": "true"},
        )
    )

    [event] = operational_store.events_for(incident_id)

    assert event.detail == {
        "outcome": "escalate",
        "policy_rule": "G_PENDING",
        "in_scope": "true",
    }

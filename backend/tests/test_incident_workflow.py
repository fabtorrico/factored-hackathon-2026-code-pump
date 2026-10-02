"""End-to-end incident workflow scenarios.

Synthetic fixtures only: every row comes from the curated pipeline built on conftest's synthetic
CSV sources. No organizer records, no LLM, no customer-facing prose.
"""

import sqlite3

import pytest
from conftest import ABSENT_CUSTOMER, OTHER, OWNER, SESSION_TTL

from app.banking.errors import InvalidRequestError
from app.banking.models import CandidateFilters
from app.banking.service import BankingService
from app.data.contracts import TRANSACTIONS
from app.policy import PolicyOutcome, PolicyReasonCode, PolicyRule
from app.workflow.models import (
    ClarificationReason,
    IncidentInput,
    SupportCase,
    SupportRoute,
    UnresolvedQuestion,
    WorkflowAction,
    WorkflowEventType,
    WorkflowFailureReason,
    WorkflowStatus,
)
from app.workflow.orchestrator import IncidentWorkflow
from app.workflow.storage import OperationalStore

DECLINED = "TXN-002"
PENDING = "TXN-003"
APPROVED = "TXN-001"
REVERSED = "TXN-007"
ABSENT_TRANSACTION = "TXN-999"
FOREIGN_TRANSACTION = "TXN-004"


class SilentCaseStore(OperationalStore):
    """Accepts the write and persists nothing, so the readback cannot confirm it."""

    def create_support_case(self, case: SupportCase) -> None:
        return None


class MismatchedCaseStore(OperationalStore):
    """Persists the case but reports a different incident on readback."""

    def get_support_case(self, case_id: str) -> SupportCase | None:
        case = super().get_support_case(case_id)
        return None if case is None else case.model_copy(update={"incident_id": "INC-OTHER"})


class SilentHandoffStore(OperationalStore):
    """Accepts the handoff write and persists nothing, so the readback cannot confirm it."""

    def save_handoff(self, handoff, created_at) -> None:
        return None


def _events(store: OperationalStore, incident_id: str) -> list[str]:
    return [event.event_type.value for event in store.events_for(incident_id)]


def _case_count(store: OperationalStore) -> int:
    with sqlite3.connect(store.database_path) as connection:
        return int(connection.execute("SELECT count(*) FROM support_cases").fetchone()[0])


# --- Exact transaction, Declined ------------------------------------------------------


def test_declined_transaction_resolves_with_verified_facts(workflow, incident_session) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    assert result.status is WorkflowStatus.COMPLETED
    assert result.policy_decision.outcome is PolicyOutcome.RESOLVE
    assert result.policy_decision.reason_code is PolicyReasonCode.DECLINED_STATUS
    assert result.policy_decision.policy_rule is PolicyRule.F_DECLINED
    assert result.verified_transaction is not None
    assert result.verified_transaction.transaction_status == "Declined"
    assert result.verified_transaction.customer_id == OWNER


@pytest.fixture
def workflow_without_data(service_without_data, operational_store, clock) -> IncidentWorkflow:
    return IncidentWorkflow(service=service_without_data, store=operational_store, clock=clock)


@pytest.fixture
def data_session(service_without_data) -> str:
    return service_without_data.create_session(OWNER).session_id


def test_resolution_creates_no_support_case(workflow, incident_session, operational_store) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    assert result.support_case is None
    assert result.handoff is None
    assert _case_count(operational_store) == 0
    assert "workflow_escalated" not in _events(operational_store, result.incident_id)


def test_resolution_persists_the_incident(workflow, incident_session, operational_store) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    incident = operational_store.get_incident(result.incident_id)

    assert incident is not None
    assert incident.customer_id == OWNER
    assert incident.status is WorkflowStatus.COMPLETED
    assert incident.outcome is PolicyOutcome.RESOLVE
    assert incident.transaction_id == DECLINED
    assert incident.policy_rule is PolicyRule.F_DECLINED


def test_resolution_invents_no_decline_cause(workflow, incident_session) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    record = result.verified_transaction
    assert record.response_code == "51"  # recorded verbatim, never interpreted
    # Only curated columns and the policy decision cross the workflow boundary: no sentence, no
    # cause, no customer-facing text.
    assert set(record.model_dump(exclude_none=True)) == set(TRANSACTIONS.curated_columns)
    assert set(result.model_dump(exclude_none=True)) == {
        "incident_id",
        "status",
        "created_at",
        "policy_decision",
        "verified_transaction",
    }


def test_resolution_can_be_read_as_a_status_level_answer(workflow, incident_session) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    decision = result.policy_decision
    assert decision.policy_version == "1.0.0"
    # The only authorized claim is the recorded status.
    assert result.verified_transaction.transaction_status == "Declined"


# --- Exact transaction, Pending -------------------------------------------------------


def test_pending_transaction_escalates_with_a_verified_case(
    workflow, incident_session, operational_store
) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    assert result.status is WorkflowStatus.COMPLETED
    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.policy_rule is PolicyRule.G_PENDING
    assert result.failure is None
    assert result.support_case is not None
    assert result.support_case.recommended_route is SupportRoute.PAYMENTS_OPERATIONS
    persisted = operational_store.get_support_case(result.support_case.case_id)
    assert persisted == result.support_case
    assert persisted.incident_id == result.incident_id


def test_pending_escalation_records_the_whole_action_and_verification(
    workflow, incident_session, operational_store
) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    assert _events(operational_store, result.incident_id) == [
        WorkflowEventType.INCIDENT_CREATED.value,
        WorkflowEventType.TRANSACTION_VERIFIED.value,
        WorkflowEventType.POLICY_EVALUATED.value,
        WorkflowEventType.SUPPORT_CASE_CREATION_ATTEMPTED.value,
        WorkflowEventType.SUPPORT_CASE_CREATED.value,
        WorkflowEventType.SUPPORT_CASE_VERIFIED.value,
        WorkflowEventType.WORKFLOW_ESCALATED.value,
    ]


def test_pending_handoff_is_structured_and_grounded(workflow, incident_session) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    handoff = result.handoff
    assert handoff is not None
    assert handoff.case_id == result.support_case.case_id
    assert handoff.incident_id == result.incident_id
    assert handoff.recommended_route is SupportRoute.PAYMENTS_OPERATIONS
    assert handoff.customer_request.identification_mode.value == "exact_transaction"
    assert handoff.customer_request.transaction_reference == PENDING
    assert handoff.unresolved_questions == (UnresolvedQuestion.FINAL_SETTLEMENT_STATE_UNAVAILABLE,)
    assert WorkflowAction.SUPPORT_CASE_VERIFIED in handoff.actions_taken
    assert WorkflowAction.POLICY_EVALUATED in handoff.actions_taken
    statuses = {fact.fact: fact.value for fact in handoff.verified_facts}
    assert statuses["transaction_status"] == "Pending"
    assert statuses["transaction_ownership_verified"] == "true"
    assert statuses["authenticated_customer_verified"] == "true"


# --- Exact transaction, Reversed ------------------------------------------------------


def test_reversed_transaction_escalates(workflow, incident_session) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=REVERSED))

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.reason_code is PolicyReasonCode.REVERSED_STATUS
    assert result.support_case is not None


def test_reversed_handoff_distinguishes_status_from_returned_funds(
    workflow, incident_session
) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=REVERSED))

    handoff = result.handoff
    assert handoff is not None
    assert handoff.unresolved_questions == (
        UnresolvedQuestion.RETURNED_FUNDS_NOT_INDEPENDENTLY_VERIFIED,
    )
    facts = {fact.fact: fact.value for fact in handoff.verified_facts}
    assert facts["transaction_status"] == "Reversed"
    assert "returned_funds" not in facts
    assert "funds_returned" not in facts
    # The recorded response code is absent on this row, so no evidence entry is invented.
    assert all(
        evidence.kind != "transaction_response_code" for evidence in handoff.supporting_evidence
    )


# --- Approved -------------------------------------------------------------------------


def test_approved_with_unresolved_issue_escalates(workflow, incident_session) -> None:
    result = workflow.handle(
        incident_session,
        IncidentInput(transaction_id=APPROVED, approved_with_unresolved_issue=True),
    )

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.reason_code is PolicyReasonCode.APPROVED_UNRESOLVED_ISSUE
    handoff = result.handoff
    assert handoff is not None
    assert handoff.unresolved_questions == (
        UnresolvedQuestion.UNRESOLVED_ISSUE_ON_APPROVED_TRANSACTION,
    )
    assert handoff.customer_request.approved_with_unresolved_issue is True


def test_approved_without_incident_abstains(workflow, incident_session, operational_store) -> None:
    result = workflow.handle(incident_session, IncidentInput(transaction_id=APPROVED))

    assert result.policy_decision.outcome is PolicyOutcome.ABSTAIN
    assert result.policy_decision.reason_code is PolicyReasonCode.APPROVED_NO_SUPPORTED_INCIDENT
    assert result.support_case is None
    assert result.handoff is None
    incident = operational_store.get_incident(result.incident_id)
    assert incident.status is WorkflowStatus.COMPLETED
    assert incident.outcome is PolicyOutcome.ABSTAIN


# --- Ambiguity ------------------------------------------------------------------------


def test_zero_candidates_clarifies_without_inventing_options(
    workflow, incident_session, operational_store
) -> None:
    result = workflow.handle(
        incident_session, IncidentInput(filters=CandidateFilters(transaction_type="Withdrawal"))
    )

    assert result.policy_decision.outcome is PolicyOutcome.CLARIFY
    assert result.policy_decision.reason_code is PolicyReasonCode.NO_MATCHING_TRANSACTION
    assert result.clarification.reason is ClarificationReason.NO_MATCHING_TRANSACTION
    assert result.clarification.candidates == ()
    assert result.support_case is None
    incident = operational_store.get_incident(result.incident_id)
    assert incident.outcome is PolicyOutcome.CLARIFY
    assert incident.transaction_id is None


def test_multiple_candidates_clarify_and_are_never_auto_selected(
    workflow, incident_session
) -> None:
    result = workflow.handle(
        incident_session, IncidentInput(filters=CandidateFilters(transaction_type="Payment"))
    )

    assert result.policy_decision.outcome is PolicyOutcome.CLARIFY
    assert result.policy_decision.reason_code is PolicyReasonCode.MULTIPLE_CANDIDATE_TRANSACTIONS
    assert result.clarification.reason is ClarificationReason.MULTIPLE_CANDIDATE_TRANSACTIONS
    offered = [candidate.transaction_id for candidate in result.clarification.candidates]
    assert offered == ["TXN-008", REVERSED, DECLINED]
    assert result.verified_transaction is None
    assert result.support_case is None


def test_clarification_summaries_are_minimal(workflow, incident_session) -> None:
    result = workflow.handle(
        incident_session, IncidentInput(filters=CandidateFilters(transaction_type="Payment"))
    )

    for candidate in result.clarification.candidates:
        assert set(candidate.model_dump(exclude_none=True)) == {
            "transaction_id",
            "transaction_status",
            "transaction_type",
            "amount",
            "currency",
            "transaction_date",
        }
        assert "customer_id" not in candidate.model_dump()


def test_foreign_candidates_are_never_offered(workflow, other_incident_session) -> None:
    result = workflow.handle(
        other_incident_session, IncidentInput(filters=CandidateFilters(transaction_type="Transfer"))
    )

    offered = [candidate.transaction_id for candidate in result.clarification.candidates]
    assert offered == ["TXN-005", "TXN-006"]
    assert DECLINED not in offered
    assert REVERSED not in offered


def test_a_single_candidate_search_escalates_without_an_exact_reference(
    workflow, incident_session
) -> None:
    result = workflow.handle(
        incident_session, IncidentInput(filters=CandidateFilters(transaction_status="Reversed"))
    )

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.reason_code is PolicyReasonCode.REVERSED_STATUS
    assert result.verified_transaction.transaction_id == REVERSED


# --- Security -------------------------------------------------------------------------


@pytest.mark.parametrize("session_id", [None, "", "   ", "forged-session"])
def test_invalid_session_abstains_without_touching_banking_data(
    workflow, session_id, audit_sink
) -> None:
    result = workflow.handle(session_id, IncidentInput(transaction_id=DECLINED))

    assert result.policy_decision.outcome is PolicyOutcome.ABSTAIN
    assert result.policy_decision.reason_code is PolicyReasonCode.INVALID_SESSION
    assert result.policy_decision.policy_rule is PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW
    assert result.verified_transaction is None
    assert result.support_case is None
    # No banking tool ran, so no customer facts were ever requested.
    assert audit_sink.recent(limit=10) == []


def test_expired_session_abstains(workflow, incident_session, clock, operational_store) -> None:
    clock.advance(SESSION_TTL)

    result = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    assert result.policy_decision.outcome is PolicyOutcome.ABSTAIN
    assert result.policy_decision.reason_code is PolicyReasonCode.INVALID_SESSION
    assert result.verified_transaction is None
    assert operational_store.get_incident(result.incident_id).customer_id is None


def test_unauthorized_exact_transaction_looks_absent(workflow, incident_session) -> None:
    foreign = workflow.handle(incident_session, IncidentInput(transaction_id=FOREIGN_TRANSACTION))
    absent = workflow.handle(incident_session, IncidentInput(transaction_id=ABSENT_TRANSACTION))

    for result in (foreign, absent):
        assert result.policy_decision.outcome is PolicyOutcome.CLARIFY
        assert result.policy_decision.reason_code is PolicyReasonCode.NO_MATCHING_TRANSACTION
        assert result.verified_transaction is None
        assert result.support_case is None
    assert (
        foreign.policy_decision.reason_code is absent.policy_decision.reason_code
        and foreign.policy_decision.policy_rule is absent.policy_decision.policy_rule
    )


def test_session_for_an_absent_customer_still_only_sees_its_own_rows(
    incident_service, operational_store, clock
) -> None:
    workflow = IncidentWorkflow(service=incident_service, store=operational_store, clock=clock)
    session = incident_service.create_session(ABSENT_CUSTOMER).session_id

    result = workflow.handle(session, IncidentInput(transaction_id=APPROVED))

    assert result.policy_decision.outcome is PolicyOutcome.CLARIFY
    assert result.verified_transaction is None


def test_rejected_request_keeps_its_banking_core_error(workflow, incident_session) -> None:
    with pytest.raises(InvalidRequestError):
        workflow.handle(
            incident_session,
            IncidentInput(filters=CandidateFilters(transaction_status="Escheated")),
        )


# --- Tool and data failure ------------------------------------------------------------


def test_banking_data_failure_escalates_and_is_not_a_clarification(
    workflow_without_data, data_session
) -> None:
    result = workflow_without_data.handle(data_session, IncidentInput(transaction_id=DECLINED))

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.reason_code is PolicyReasonCode.TOOL_FAILURE_EXHAUSTED
    assert result.policy_decision.policy_rule is PolicyRule.C_TOOL_FAILURE
    assert result.clarification is None
    assert result.verified_transaction is None
    assert result.support_case is not None


def test_banking_data_failure_never_becomes_a_candidate_search(
    workflow_without_data, data_session, operational_store
) -> None:
    result = workflow_without_data.handle(
        data_session, IncidentInput(filters=CandidateFilters(transaction_type="Payment"))
    )

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.policy_decision.reason_code is PolicyReasonCode.TOOL_FAILURE_EXHAUSTED
    assert result.policy_decision.policy_rule is PolicyRule.C_TOOL_FAILURE
    assert result.clarification is None
    events = _events(operational_store, result.incident_id)
    assert WorkflowEventType.BANKING_LOOKUP_FAILED.value in events
    assert WorkflowEventType.CANDIDATE_SEARCH_COMPLETED.value not in events
    lookup = next(
        event
        for event in operational_store.events_for(result.incident_id)
        if event.event_type is WorkflowEventType.BANKING_LOOKUP_FAILED
    )
    assert lookup.detail == {"reason": "data_unavailable"}


def test_banking_data_failure_handoff_states_no_transaction_was_verified(
    workflow_without_data, data_session
) -> None:
    result = workflow_without_data.handle(data_session, IncidentInput(transaction_id=DECLINED))

    handoff = result.handoff
    assert handoff is not None
    facts = {fact.fact: fact.value for fact in handoff.verified_facts}
    assert facts["banking_data_available"] == "false"
    assert "transaction_status" not in facts
    assert "transaction_ownership_verified" not in facts
    assert handoff.supporting_evidence == ()
    assert handoff.unresolved_questions == (UnresolvedQuestion.BANKING_DATA_UNAVAILABLE,)
    assert WorkflowAction.BANKING_LOOKUP_FAILED in handoff.actions_taken


# --- Act then verify ------------------------------------------------------------------


@pytest.fixture
def silent_store(tmp_path) -> OperationalStore:
    store = SilentCaseStore(tmp_path / "operational" / "app.db")
    store.initialize()
    return store


@pytest.fixture
def mismatched_store(tmp_path) -> OperationalStore:
    store = MismatchedCaseStore(tmp_path / "operational" / "app.db")
    store.initialize()
    return store


@pytest.fixture
def silent_handoff_store(tmp_path) -> OperationalStore:
    store = SilentHandoffStore(tmp_path / "operational" / "app.db")
    store.initialize()
    return store


@pytest.mark.parametrize("store_fixture", ["silent_store", "mismatched_store"])
def test_unverifiable_case_never_reports_an_escalation(
    request, incident_service, clock, store_fixture, incident_session
) -> None:
    workflow = IncidentWorkflow(
        service=incident_service, store=request.getfixturevalue(store_fixture), clock=clock
    )

    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    assert result.policy_decision.outcome is PolicyOutcome.ESCALATE
    assert result.status is WorkflowStatus.FAILED
    assert result.failure.reason is WorkflowFailureReason.SUPPORT_CASE_UNVERIFIED
    assert result.support_case is None
    assert result.handoff is None


def test_unverifiable_handoff_never_reports_a_completed_escalation(
    silent_handoff_store, incident_service, clock, incident_session
) -> None:
    # The case is written and verified, but the handoff that a human agent reads cannot be. The
    # escalation is not claimed, so the persisted handoff invariant holds.
    workflow = IncidentWorkflow(service=incident_service, store=silent_handoff_store, clock=clock)

    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    assert result.status is WorkflowStatus.FAILED
    assert result.failure.reason is WorkflowFailureReason.SUPPORT_CASE_UNVERIFIED
    assert result.support_case is None
    assert result.handoff is None
    events = _events(silent_handoff_store, result.incident_id)
    assert WorkflowEventType.SUPPORT_CASE_VERIFICATION_FAILED.value in events
    assert WorkflowEventType.WORKFLOW_FAILED.value in events
    assert WorkflowEventType.WORKFLOW_ESCALATED.value not in events


def test_unverifiable_case_is_recorded_as_a_failure(silent_store, incident_service, clock):
    workflow = IncidentWorkflow(service=incident_service, store=silent_store, clock=clock)
    session = incident_service.create_session(OWNER).session_id

    result = workflow.handle(session, IncidentInput(transaction_id=PENDING))

    events = _events(silent_store, result.incident_id)
    assert WorkflowEventType.SUPPORT_CASE_CREATION_ATTEMPTED.value in events
    assert WorkflowEventType.SUPPORT_CASE_VERIFICATION_FAILED.value in events
    assert WorkflowEventType.WORKFLOW_FAILED.value in events
    assert WorkflowEventType.WORKFLOW_ESCALATED.value not in events
    assert silent_store.get_incident(result.incident_id).status is WorkflowStatus.FAILED


# --- Audit ----------------------------------------------------------------------------


def test_workflow_events_carry_no_customer_data(workflow, incident_session, operational_store):
    result = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    events = operational_store.events_for(result.incident_id)
    payload = repr([event.model_dump() for event in events])

    assert events
    assert "@example.com" not in payload
    assert "Samuel" not in payload
    assert "G8637940" not in payload  # document number from the raw source
    assert incident_session not in payload


def test_banking_tool_audit_is_still_recorded(workflow, incident_session, audit_sink) -> None:
    workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    tools = {event.tool for event in audit_sink.recent(limit=5)}
    assert tools == {"get_transaction"}


# --- Scope ----------------------------------------------------------------------------


def test_out_of_scope_incident_abstains(workflow, incident_session, operational_store) -> None:
    result = workflow.handle(
        incident_session, IncidentInput(transaction_id=DECLINED, in_scope=False)
    )

    assert result.policy_decision.outcome is PolicyOutcome.ABSTAIN
    assert result.policy_decision.reason_code is PolicyReasonCode.OUT_OF_SCOPE
    assert result.support_case is None
    assert operational_store.get_incident(result.incident_id).outcome is PolicyOutcome.ABSTAIN


def test_two_runs_of_the_same_incident_are_independent(workflow, incident_session) -> None:
    first = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))
    second = workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    assert first.incident_id != second.incident_id
    assert first.policy_decision == second.policy_decision
    assert first.verified_transaction == second.verified_transaction


def test_identifiers_carry_no_incident_content(workflow, incident_session) -> None:
    escalated = workflow.handle(incident_session, IncidentInput(transaction_id=PENDING))

    for identifier in (escalated.incident_id, escalated.support_case.case_id):
        assert identifier not in {OWNER, OTHER, PENDING}
        for fragment in (OWNER, OTHER, PENDING, "Pending", "ESCALATE"):
            assert fragment not in identifier


def test_service_is_the_only_banking_reader(
    incident_service, workflow, incident_session, monkeypatch
) -> None:
    service: BankingService = incident_service
    calls: list[str] = []
    original = service.get_transaction

    def spy(session_id, transaction_id):
        calls.append(transaction_id)
        return original(session_id, transaction_id)

    monkeypatch.setattr(service, "get_transaction", spy)
    workflow.handle(incident_session, IncidentInput(transaction_id=DECLINED))

    assert calls == [DECLINED]

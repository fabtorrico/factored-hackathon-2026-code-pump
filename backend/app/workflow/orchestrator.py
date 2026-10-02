"""Deterministic incident workflow.

    validate session -> identify candidate(s) -> read verified banking facts -> map to
    PolicyContext -> evaluate Synthetic Banking Policy v1 -> perform the permitted action ->
    verify the action -> return the structured result

The Policy Engine is the only component that decides an outcome. This module coordinates the
Banking Core, the policy engine, operational persistence and workflow events; it never reads the
curated database itself, never re-derives authorization, ownership or a transaction cause, and
never claims an action succeeded without reading it back.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.banking.errors import BankingError, IncidentNotFoundError, Reason
from app.banking.models import TransactionRecord
from app.banking.service import BankingService
from app.policy import PolicyDecision, PolicyOutcome, evaluate_policy
from app.workflow.handoff import build_handoff
from app.workflow.mapping import VerifiedWorkflowState, to_policy_context
from app.workflow.models import (
    CaseStatus,
    Clarification,
    ClarificationCandidate,
    ClarificationReason,
    Incident,
    IncidentInput,
    IncidentSummary,
    SupportCase,
    SupportRoute,
    WorkflowAction,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowFailure,
    WorkflowFailureReason,
    WorkflowResult,
    WorkflowStatus,
    new_case_id,
    new_incident_id,
)
from app.workflow.storage import OperationalStore, OperationalStoreError

# A denial is never softened into a workflow outcome: invalid, expired and unauthorized sessions
# keep the Banking Core's own error and HTTP semantics.
FAILURE_REASONS = frozenset({Reason.DATA_UNAVAILABLE, Reason.TOOL_FAILURE})
# A Banking Core 404 collapses absent and foreign transactions on purpose, so the workflow can
# only observe "no owned candidate". Re-raising it here would leak the difference through the HTTP
# status while adding nothing the workflow could use.
VERIFIED_EMPTY_REASONS = frozenset({Reason.TRANSACTION_NOT_FOUND, Reason.CUSTOMER_NOT_FOUND})


def _summary(request: IncidentInput) -> IncidentSummary:
    return IncidentSummary(
        identification_mode=request.identification_mode,
        transaction_reference=request.transaction_id,
        filters=request.filters,
        in_scope=request.in_scope,
        approved_with_unresolved_issue=request.approved_with_unresolved_issue,
    )


def _candidate_summary(record: TransactionRecord) -> ClarificationCandidate:
    return ClarificationCandidate(
        transaction_id=record.transaction_id,
        transaction_status=record.transaction_status,
        transaction_type=record.transaction_type,
        amount=record.amount,
        currency=record.currency,
        transaction_date=record.transaction_date,
    )


class Identification:
    """What the Banking Core actually returned: the state to map, plus the authorized records."""

    __slots__ = ("actions", "records", "state")

    def __init__(
        self,
        state: VerifiedWorkflowState,
        records: tuple[TransactionRecord, ...],
        actions: tuple[WorkflowAction, ...],
    ) -> None:
        self.state = state
        self.records = records
        self.actions = actions

    @property
    def record(self) -> TransactionRecord | None:
        return self.state.verified_transaction

    @staticmethod
    def unauthenticated(request: IncidentInput) -> Identification:
        # Nothing about the customer or the transaction was established, so the state asserts
        # only what was observed: an unusable session and no candidates.
        return Identification(
            state=VerifiedWorkflowState(
                session_valid=False,
                authorized=False,
                in_scope=request.in_scope,
                authenticated_customer_id=None,
                candidate_transaction_count=0,
                verified_transaction=None,
                approved_with_unresolved_issue=request.approved_with_unresolved_issue,
                tool_failure_exhausted=False,
                required_evidence_missing=False,
            ),
            records=(),
            actions=(),
        )


class IncidentWorkflow:
    """Stateless orchestrator: all state lives in the operational store and the Banking Core."""

    def __init__(
        self,
        service: BankingService,
        store: OperationalStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._store = store
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    def handle(self, session_id: str | None, request: IncidentInput) -> WorkflowResult:
        incident_id = new_incident_id()
        created_at = self._clock()
        summary = _summary(request)
        self._record(
            incident_id,
            WorkflowEventType.INCIDENT_CREATED,
            {
                "identification_mode": summary.identification_mode.value,
                "in_scope": str(summary.in_scope).lower(),
                "approved_with_unresolved_issue": str(
                    summary.approved_with_unresolved_issue
                ).lower(),
            },
        )
        identification = self._identify(incident_id, session_id, request)
        decision = evaluate_policy(to_policy_context(identification.state))
        self._record(
            incident_id,
            WorkflowEventType.POLICY_EVALUATED,
            {
                "outcome": decision.outcome.value,
                "reason_code": decision.reason_code.value,
                "policy_rule": decision.policy_rule.value,
                "policy_version": decision.policy_version,
            },
        )
        self._open_incident(incident_id, created_at, identification, decision)
        result = self._perform(incident_id, created_at, summary, identification, decision)
        self._store.finalize_incident(incident_id, result.status)
        return result

    def timeline(self, session_id: str | None, incident_id: str) -> tuple[WorkflowEvent, ...]:
        """The recorded steps of one incident, for the customer who raised it.

        Read-only and owner-scoped: the session is resolved against the same SessionStore the
        banking tools authenticate against, and an incident that does not exist is reported exactly
        like one owned by somebody else, so this cannot be used to discover incident ids.
        """
        customer_id = self._service.sessions.resolve(session_id).customer_id
        incident = self._store.get_incident(incident_id)
        if incident is None or incident.customer_id != customer_id:
            raise IncidentNotFoundError(f"incident {incident_id} is not owned by {customer_id}")
        return tuple(self._store.events_for(incident_id))

    # --- Banking reads --------------------------------------------------------------------

    def _identify(
        self, incident_id: str, session_id: str | None, request: IncidentInput
    ) -> Identification:
        # The same SessionStore instance the banking tools authenticate against, so the workflow
        # can never hold an identity the Banking Core would reject.
        customer_id = self._authenticated_customer(session_id)
        if customer_id is None:
            return Identification.unauthenticated(request)
        try:
            records = self._read_candidates(session_id, request)
        except BankingError as error:
            if error.reason in FAILURE_REASONS:
                self._record(
                    incident_id,
                    WorkflowEventType.BANKING_LOOKUP_FAILED,
                    {"reason": error.reason.value},
                )
                return Identification(
                    state=VerifiedWorkflowState(
                        session_valid=True,
                        authorized=True,
                        in_scope=request.in_scope,
                        authenticated_customer_id=customer_id,
                        candidate_transaction_count=0,
                        verified_transaction=None,
                        approved_with_unresolved_issue=request.approved_with_unresolved_issue,
                        tool_failure_exhausted=True,
                        # Phase 3B requires no evidence beyond verified identity, ownership and
                        # status, so no evidence rule is ever raised here.
                        required_evidence_missing=False,
                    ),
                    records=(),
                    actions=(
                        WorkflowAction.SESSION_VALIDATED,
                        WorkflowAction.BANKING_LOOKUP_FAILED,
                    ),
                )
            if error.reason in VERIFIED_EMPTY_REASONS:
                records = ()
            else:
                # Denials keep their Banking Core semantics: 401, 403 and 400 are never softened
                # into a workflow outcome.
                raise
        return self._identified(incident_id, customer_id, request, records)

    def _read_candidates(
        self, session_id: str | None, request: IncidentInput
    ) -> tuple[TransactionRecord, ...]:
        if request.transaction_id is not None:
            record = self._service.get_transaction(session_id, request.transaction_id)
            return (record,)
        search = self._service.find_candidate_transactions(session_id, request.filters)
        return tuple(search.candidates)

    def _identified(
        self,
        incident_id: str,
        customer_id: str,
        request: IncidentInput,
        records: tuple[TransactionRecord, ...],
    ) -> Identification:
        record = records[0] if len(records) == 1 else None
        actions = [WorkflowAction.SESSION_VALIDATED]
        if request.transaction_id is None:
            self._record(
                incident_id,
                WorkflowEventType.CANDIDATE_SEARCH_COMPLETED,
                {"candidate_count": str(len(records))},
            )
            actions.append(WorkflowAction.CANDIDATE_SEARCH_COMPLETED)
        if record is not None:
            self._record(
                incident_id,
                WorkflowEventType.TRANSACTION_VERIFIED,
                {"transaction_id": record.transaction_id},
            )
            actions.append(WorkflowAction.TRANSACTION_VERIFIED)
        return Identification(
            state=VerifiedWorkflowState(
                session_valid=True,
                authorized=True,
                in_scope=request.in_scope,
                authenticated_customer_id=customer_id,
                candidate_transaction_count=len(records),
                verified_transaction=record,
                approved_with_unresolved_issue=request.approved_with_unresolved_issue,
                tool_failure_exhausted=False,
                required_evidence_missing=False,
            ),
            records=records,
            actions=tuple(actions),
        )

    def _authenticated_customer(self, session_id: str | None) -> str | None:
        try:
            return self._service.sessions.resolve(session_id).customer_id
        except BankingError:
            return None

    # --- Permitted action and verification ------------------------------------------------

    def _perform(
        self,
        incident_id: str,
        created_at: datetime,
        summary: IncidentSummary,
        identification: Identification,
        decision: PolicyDecision,
    ) -> WorkflowResult:
        if decision.outcome is PolicyOutcome.ESCALATE:
            return self._escalate(incident_id, created_at, summary, identification, decision)
        if decision.outcome is PolicyOutcome.CLARIFY:
            return self._clarify(incident_id, created_at, identification, decision)
        return self._conclude(incident_id, created_at, identification, decision)

    def _escalate(
        self,
        incident_id: str,
        created_at: datetime,
        summary: IncidentSummary,
        identification: Identification,
        decision: PolicyDecision,
    ) -> WorkflowResult:
        case = SupportCase(
            case_id=new_case_id(),
            incident_id=incident_id,
            status=CaseStatus.OPEN,
            recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
            created_at=created_at,
        )
        self._record(
            incident_id,
            WorkflowEventType.SUPPORT_CASE_CREATION_ATTEMPTED,
            {"case_id": case.case_id, "recommended_route": case.recommended_route.value},
        )
        try:
            self._store.create_support_case(case)
            persisted = self._store.get_support_case(case.case_id)
        except OperationalStoreError:
            # The write itself failed, so there is nothing to read back and nothing to retry.
            return self._case_unverified(incident_id, created_at, case, identification, decision)
        verified = (
            persisted is not None
            and persisted.incident_id == case.incident_id
            and persisted.status is case.status
            and persisted.recommended_route is case.recommended_route
        )
        if not verified:
            # A write that cannot be read back is not an escalation. Report a workflow failure
            # and keep the incident on record as failed; no retry is attempted.
            return self._case_unverified(incident_id, created_at, case, identification, decision)
        actions = (
            *identification.actions,
            WorkflowAction.POLICY_EVALUATED,
            WorkflowAction.SUPPORT_CASE_CREATED,
        )
        self._record(incident_id, WorkflowEventType.SUPPORT_CASE_CREATED, {"case_id": case.case_id})
        self._record(
            incident_id,
            WorkflowEventType.SUPPORT_CASE_VERIFIED,
            {"case_id": case.case_id, "recommended_route": case.recommended_route.value},
        )
        self._record(
            incident_id,
            WorkflowEventType.WORKFLOW_ESCALATED,
            {"case_id": case.case_id, "recommended_route": case.recommended_route.value},
        )
        handoff = build_handoff(
            incident_id=incident_id,
            case_id=case.case_id,
            request=summary,
            decision=decision,
            session_valid=True,
            record=identification.record,
            actions=(*actions, WorkflowAction.SUPPORT_CASE_VERIFIED),
        )
        return WorkflowResult(
            incident_id=incident_id,
            status=WorkflowStatus.COMPLETED,
            created_at=created_at,
            policy_decision=decision,
            verified_transaction=identification.record,
            support_case=case,
            handoff=handoff,
        )

    def _case_unverified(
        self,
        incident_id: str,
        created_at: datetime,
        case: SupportCase,
        identification: Identification,
        decision: PolicyDecision,
    ) -> WorkflowResult:
        self._record(
            incident_id,
            WorkflowEventType.SUPPORT_CASE_VERIFICATION_FAILED,
            {"case_id": case.case_id},
        )
        self._record(incident_id, WorkflowEventType.WORKFLOW_FAILED, {})
        return WorkflowResult(
            incident_id=incident_id,
            status=WorkflowStatus.FAILED,
            created_at=created_at,
            policy_decision=decision,
            verified_transaction=identification.record,
            failure=WorkflowFailure(reason=WorkflowFailureReason.SUPPORT_CASE_UNVERIFIED),
        )

    def _clarify(
        self,
        incident_id: str,
        created_at: datetime,
        identification: Identification,
        decision: PolicyDecision,
    ) -> WorkflowResult:
        multiple = len(identification.records) > 1
        self._record(
            incident_id,
            WorkflowEventType.WORKFLOW_CLARIFICATION_REQUIRED,
            {"candidate_count": str(len(identification.records))},
        )
        return WorkflowResult(
            incident_id=incident_id,
            status=WorkflowStatus.COMPLETED,
            created_at=created_at,
            policy_decision=decision,
            clarification=Clarification(
                reason=(
                    ClarificationReason.MULTIPLE_CANDIDATE_TRANSACTIONS
                    if multiple
                    else ClarificationReason.NO_MATCHING_TRANSACTION
                ),
                # Zero candidates fabricate no options, and several candidates are never resolved
                # into one automatically.
                candidates=tuple(_candidate_summary(record) for record in identification.records),
            ),
        )

    def _conclude(
        self,
        incident_id: str,
        created_at: datetime,
        identification: Identification,
        decision: PolicyDecision,
    ) -> WorkflowResult:
        self._record(
            incident_id,
            (
                WorkflowEventType.WORKFLOW_RESOLVED
                if decision.outcome is PolicyOutcome.RESOLVE
                else WorkflowEventType.WORKFLOW_ABSTAINED
            ),
            {},
        )
        return WorkflowResult(
            incident_id=incident_id,
            status=WorkflowStatus.COMPLETED,
            created_at=created_at,
            policy_decision=decision,
            # Grounded facts only. A resolution asserts the recorded status, never a cause, and
            # never generates the customer-facing sentence itself.
            verified_transaction=identification.record,
        )

    # --- Operational state ---------------------------------------------------------------

    def _open_incident(
        self,
        incident_id: str,
        created_at: datetime,
        identification: Identification,
        decision: PolicyDecision,
    ) -> None:
        # Written before the permitted action runs, so a support case can only ever belong to an
        # incident that is already on record. The terminal status is set once the action is done.
        record = identification.record
        self._store.save_incident(
            Incident(
                incident_id=incident_id,
                customer_id=identification.state.authenticated_customer_id,
                created_at=created_at,
                status=WorkflowStatus.OPEN,
                outcome=decision.outcome,
                reason_code=decision.reason_code,
                policy_rule=decision.policy_rule,
                transaction_id=record.transaction_id if record is not None else None,
            )
        )

    def _record(
        self, incident_id: str, event_type: WorkflowEventType, detail: dict[str, str] | None = None
    ) -> None:
        self._store.record_event(
            WorkflowEvent(
                incident_id=incident_id,
                occurred_at=self._clock(),
                event_type=event_type,
                detail=detail or {},
            )
        )

"""Read-only views over persisted operational cases, for a human agent.

The workspace reads only the local operational store: support cases, the incident behind each one,
the structured handoff written at escalation and the recorded workflow events. It never opens the
curated banking database, so an agent cannot use it as a second, unaudited banking read.

A case is listed because a support case row exists, never because a fixture invented one. Detail
reports a missing handoff honestly rather than reconstructing facts it cannot prove.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agent.sessions import AgentSession, AgentSessionStore
from app.banking.errors import CaseNotFoundError
from app.policy import PolicyOutcome, PolicyReasonCode, PolicyRule
from app.workflow.models import (
    CaseStatus,
    Handoff,
    Incident,
    SupportCase,
    SupportRoute,
    WorkflowEvent,
    WorkflowStatus,
)
from app.workflow.storage import OperationalStore


class AgentMovementSummary(BaseModel):
    """The movement as the handoff recorded it, never as a fresh banking lookup."""

    model_config = ConfigDict(frozen=True)

    transaction_reference: str | None = None
    transaction_type: str | None = None
    transaction_status: str | None = None
    amount: str | None = None
    currency: str | None = None


class AgentCaseSummary(BaseModel):
    """One queue row: operational state and customer-safe context, no customer identity."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    incident_id: str
    status: CaseStatus
    workflow_status: WorkflowStatus | None = None
    outcome: PolicyOutcome | None = None
    reason_code: PolicyReasonCode | None = None
    policy_rule: PolicyRule | None = None
    policy_version: str | None = None
    recommended_route: SupportRoute
    created_at: datetime
    has_handoff: bool
    movement: AgentMovementSummary
    unresolved_count: int


class AgentCaseDetail(BaseModel):
    """A case with the persisted handoff and the full recorded timeline."""

    model_config = ConfigDict(frozen=True)

    case: AgentCaseSummary
    handoff: Handoff | None = None
    events: list[WorkflowEvent]


def _movement(handoff: Handoff | None, incident: Incident | None) -> AgentMovementSummary:
    reference = incident.transaction_id if incident is not None else None
    facts: dict[str, str | None] = {}
    if handoff is not None:
        reference = handoff.customer_request.transaction_reference or reference
        facts = {fact.fact: fact.value for fact in handoff.verified_facts}
    return AgentMovementSummary(
        transaction_reference=reference,
        transaction_type=facts.get("transaction_type"),
        transaction_status=facts.get("transaction_status"),
        amount=facts.get("transaction_amount"),
        currency=facts.get("transaction_currency"),
    )


class AgentWorkspace:
    def __init__(self, store: OperationalStore, sessions: AgentSessionStore) -> None:
        self._store = store
        self._sessions = sessions

    def open_session(self) -> AgentSession:
        return self._sessions.issue()

    def list_cases(self, agent_session_id: str | None) -> tuple[AgentCaseSummary, ...]:
        self._sessions.resolve(agent_session_id)
        return tuple(
            self._summary(
                case,
                self._store.get_handoff(case.case_id),
                self._store.get_incident(case.incident_id),
            )
            for case in self._store.list_support_cases()
        )

    def get_case(self, agent_session_id: str | None, case_id: str) -> AgentCaseDetail:
        self._sessions.resolve(agent_session_id)
        case = self._store.get_support_case(case_id)
        if case is None:
            raise CaseNotFoundError(f"case {case_id} is not on record")
        handoff = self._store.get_handoff(case_id)
        incident = self._store.get_incident(case.incident_id)
        return AgentCaseDetail(
            case=self._summary(case, handoff, incident),
            handoff=handoff,
            events=list(self._store.events_for(case.incident_id)),
        )

    @staticmethod
    def _summary(
        case: SupportCase, handoff: Handoff | None, incident: Incident | None
    ) -> AgentCaseSummary:
        return AgentCaseSummary(
            case_id=case.case_id,
            incident_id=case.incident_id,
            status=case.status,
            workflow_status=incident.status if incident is not None else None,
            outcome=incident.outcome if incident is not None else None,
            reason_code=incident.reason_code if incident is not None else None,
            policy_rule=incident.policy_rule if incident is not None else None,
            policy_version=incident.policy_version if incident is not None else None,
            recommended_route=case.recommended_route,
            created_at=case.created_at,
            has_handoff=handoff is not None,
            movement=_movement(handoff, incident),
            unresolved_count=len(handoff.unresolved_questions) if handoff is not None else 0,
        )

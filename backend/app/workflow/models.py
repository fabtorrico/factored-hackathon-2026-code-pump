"""Structured incident workflow types.

Deterministic orchestration only: no LLM, no natural-language understanding, no customer prose. A
future AI/ML component produces `IncidentInput`; this phase interprets none of it.

Two data domains meet here and never merge:

- verified banking evidence, returned by the Banking Core from the curated DuckDB tables;
- application-generated operational state, persisted in the local SQLite store.

Synthetic Banking Policy v1 is a hackathon demonstration model, not a real bank, organizer,
settlement or regulatory policy. `SupportRoute.PAYMENTS_OPERATIONS` is likewise a synthetic demo
route, not an organizer-provided bank structure.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, unique
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.banking.models import CandidateFilters, TransactionRecord
from app.policy import POLICY_VERSION, PolicyDecision, PolicyOutcome, PolicyReasonCode, PolicyRule


def new_incident_id() -> str:
    """Opaque identifier. Carries no customer, transaction, timestamp or outcome information."""

    return str(uuid4())


def new_case_id() -> str:
    return str(uuid4())


@unique
class IdentificationMode(StrEnum):
    EXACT = "exact_transaction"
    SEARCH = "candidate_search"


@unique
class WorkflowStatus(StrEnum):
    # Recorded before the permitted action runs and finalized once the action was verified.
    OPEN = "open"
    COMPLETED = "completed"
    FAILED = "failed"


@unique
class WorkflowFailureReason(StrEnum):
    SUPPORT_CASE_UNVERIFIED = "support_case_unverified"


@unique
class ClarificationReason(StrEnum):
    NO_MATCHING_TRANSACTION = "no_matching_transaction"
    MULTIPLE_CANDIDATE_TRANSACTIONS = "multiple_candidate_transactions"


@unique
class CaseStatus(StrEnum):
    OPEN = "open"


@unique
class SupportRoute(StrEnum):
    PAYMENTS_OPERATIONS = "PAYMENTS_OPERATIONS"


@unique
class FactSource(StrEnum):
    SESSION = "session"
    BANKING_CORE = "banking_core"
    WORKFLOW = "workflow"


@unique
class UnresolvedQuestion(StrEnum):
    BANKING_DATA_UNAVAILABLE = "banking_data_unavailable"
    FINAL_SETTLEMENT_STATE_UNAVAILABLE = "final_settlement_state_unavailable"
    RETURNED_FUNDS_NOT_INDEPENDENTLY_VERIFIED = "returned_funds_not_independently_verified"
    UNRESOLVED_ISSUE_ON_APPROVED_TRANSACTION = "unresolved_issue_on_approved_transaction"
    UNSUPPORTED_STATUS_REQUIRES_REVIEW = "unsupported_transaction_status_requires_review"
    REQUIRED_EVIDENCE_UNAVAILABLE = "required_evidence_unavailable"


@unique
class WorkflowAction(StrEnum):
    SESSION_VALIDATED = "session_validated"
    CANDIDATE_SEARCH_COMPLETED = "candidate_search_completed"
    TRANSACTION_VERIFIED = "transaction_verified"
    BANKING_LOOKUP_FAILED = "banking_lookup_failed"
    POLICY_EVALUATED = "policy_evaluated"
    SUPPORT_CASE_CREATED = "support_case_created"
    SUPPORT_CASE_VERIFIED = "support_case_verified"


@unique
class WorkflowEventType(StrEnum):
    INCIDENT_CREATED = "incident_created"
    CANDIDATE_SEARCH_COMPLETED = "candidate_search_completed"
    BANKING_LOOKUP_FAILED = "banking_lookup_failed"
    TRANSACTION_VERIFIED = "transaction_verified"
    POLICY_EVALUATED = "policy_evaluated"
    SUPPORT_CASE_CREATION_ATTEMPTED = "support_case_creation_attempted"
    SUPPORT_CASE_CREATED = "support_case_created"
    SUPPORT_CASE_VERIFIED = "support_case_verified"
    SUPPORT_CASE_VERIFICATION_FAILED = "support_case_verification_failed"
    WORKFLOW_RESOLVED = "workflow_resolved"
    WORKFLOW_CLARIFICATION_REQUIRED = "workflow_clarification_required"
    WORKFLOW_ESCALATED = "workflow_escalated"
    WORKFLOW_ABSTAINED = "workflow_abstained"
    WORKFLOW_FAILED = "workflow_failed"


class IncidentInput(BaseModel):
    """The complete structured incident input accepted by the workflow.

    It carries no prose, no policy outcome, no transaction status and no identity: the
    authenticated customer comes from the session and the transaction status comes from the
    Banking Core. A future AI/ML component is expected to produce this shape.

    `strict` rejects loosely typed values such as `"yes"` for a boolean, so two callers can never
    mean different things by the same request.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    in_scope: bool = True
    approved_with_unresolved_issue: bool = False
    transaction_id: str | None = None
    filters: CandidateFilters | None = None

    @model_validator(mode="after")
    def _exactly_one_identification_mode(self) -> IncidentInput:
        if (self.transaction_id is None) == (self.filters is None):
            raise ValueError("supply exactly one of transaction_id or filters")
        if self.transaction_id is not None and not self.transaction_id.strip():
            raise ValueError("transaction_id is blank")
        return self

    @property
    def identification_mode(self) -> IdentificationMode:
        return IdentificationMode.EXACT if self.transaction_id else IdentificationMode.SEARCH


class Incident(BaseModel):
    """One incident and its terminal state. Application-generated operational state only."""

    model_config = ConfigDict(frozen=True)

    incident_id: str
    customer_id: str | None
    created_at: datetime
    status: WorkflowStatus
    outcome: PolicyOutcome
    reason_code: PolicyReasonCode
    policy_rule: PolicyRule
    policy_version: Literal["1.0.0"] = POLICY_VERSION
    transaction_id: str | None = None


class SupportCase(BaseModel):
    """An escalation ticket for a human queue."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    incident_id: str
    status: CaseStatus
    recommended_route: SupportRoute
    created_at: datetime


class WorkflowEvent(BaseModel):
    """One workflow step. Identifiers and stable codes only: no prompts, no records, no prose."""

    model_config = ConfigDict(frozen=True)

    incident_id: str
    occurred_at: datetime
    event_type: WorkflowEventType
    detail: dict[str, str] = Field(default_factory=dict)


class VerifiedFact(BaseModel):
    """A fact the workflow actually verified, tagged with the layer that verified it."""

    model_config = ConfigDict(frozen=True)

    fact: str
    value: str | None = None
    source: FactSource


class Evidence(BaseModel):
    """A curated value recorded verbatim for a human reviewer. Never interpreted."""

    model_config = ConfigDict(frozen=True)

    kind: str
    value: str


class IncidentSummary(BaseModel):
    """Structured restatement of the incident request, as a case handler would read it."""

    model_config = ConfigDict(frozen=True)

    identification_mode: IdentificationMode
    transaction_reference: str | None = None
    filters: CandidateFilters | None = None
    in_scope: bool
    approved_with_unresolved_issue: bool


class Handoff(BaseModel):
    """Everything a human reviewer needs, and nothing they could mistake for a cause."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    incident_id: str
    customer_request: IncidentSummary
    verified_facts: tuple[VerifiedFact, ...]
    actions_taken: tuple[WorkflowAction, ...]
    supporting_evidence: tuple[Evidence, ...]
    unresolved_questions: tuple[UnresolvedQuestion, ...]
    policy_decision: PolicyDecision
    recommended_route: SupportRoute


class ClarificationCandidate(BaseModel):
    """Minimum an authorized customer needs in order to choose between their own candidates."""

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    transaction_status: str | None = None
    transaction_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    transaction_date: datetime | None = None


class Clarification(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: ClarificationReason
    candidates: tuple[ClarificationCandidate, ...] = ()


class WorkflowFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: WorkflowFailureReason


class WorkflowResult(BaseModel):
    """Terminal state of one incident workflow run."""

    model_config = ConfigDict(frozen=True)

    incident_id: str
    status: WorkflowStatus
    created_at: datetime
    policy_decision: PolicyDecision
    verified_transaction: TransactionRecord | None = None
    clarification: Clarification | None = None
    support_case: SupportCase | None = None
    handoff: Handoff | None = None
    failure: WorkflowFailure | None = None

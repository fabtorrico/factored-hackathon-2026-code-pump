"""Structured escalation handoff.

Structured data only: no generated prose, no chain-of-thought, no PII and no inferred cause. A
recorded `response_code` is carried verbatim because its semantics are undocumented, and every
open question is derived from the workflow state that actually occurred.
"""

from __future__ import annotations

from app.banking.models import TransactionRecord
from app.policy import PolicyDecision, PolicyReasonCode
from app.workflow.models import (
    Evidence,
    FactSource,
    Handoff,
    IncidentSummary,
    SupportRoute,
    UnresolvedQuestion,
    VerifiedFact,
    WorkflowAction,
)

# One entry per escalation reason. A question is recorded only when the reason is real, never as
# boilerplate on every case.
UNRESOLVED_BY_REASON: dict[PolicyReasonCode, tuple[UnresolvedQuestion, ...]] = {
    PolicyReasonCode.PENDING_STATUS: (UnresolvedQuestion.FINAL_SETTLEMENT_STATE_UNAVAILABLE,),
    PolicyReasonCode.REVERSED_STATUS: (
        UnresolvedQuestion.RETURNED_FUNDS_NOT_INDEPENDENTLY_VERIFIED,
    ),
    PolicyReasonCode.APPROVED_UNRESOLVED_ISSUE: (
        UnresolvedQuestion.UNRESOLVED_ISSUE_ON_APPROVED_TRANSACTION,
    ),
    PolicyReasonCode.UNKNOWN_TRANSACTION_STATUS: (
        UnresolvedQuestion.UNSUPPORTED_STATUS_REQUIRES_REVIEW,
    ),
    PolicyReasonCode.REQUIRED_EVIDENCE_MISSING: (UnresolvedQuestion.REQUIRED_EVIDENCE_UNAVAILABLE,),
    PolicyReasonCode.TOOL_FAILURE_EXHAUSTED: (UnresolvedQuestion.BANKING_DATA_UNAVAILABLE,),
}


def _amount(value: float) -> str:
    return f"{value:.2f}"


def _verified_facts(
    session_valid: bool, record: TransactionRecord | None, banking_data_unavailable: bool
) -> tuple[VerifiedFact, ...]:
    facts: list[VerifiedFact] = []
    if session_valid:
        facts.append(
            VerifiedFact(
                fact="authenticated_customer_verified", value="true", source=FactSource.SESSION
            )
        )
    if banking_data_unavailable:
        # The absence of transaction facts is itself the verified observation here.
        facts.append(
            VerifiedFact(fact="banking_data_available", value="false", source=FactSource.WORKFLOW)
        )
    if record is not None:
        facts.append(
            VerifiedFact(
                fact="transaction_ownership_verified",
                value="true",
                source=FactSource.BANKING_CORE,
            )
        )
        facts.append(
            VerifiedFact(
                fact="transaction_status",
                value=record.transaction_status,
                source=FactSource.BANKING_CORE,
            )
        )
        facts.append(
            VerifiedFact(
                fact="transaction_type",
                value=record.transaction_type,
                source=FactSource.BANKING_CORE,
            )
        )
        if record.amount is not None:
            facts.append(
                VerifiedFact(
                    fact="transaction_amount",
                    value=_amount(record.amount),
                    source=FactSource.BANKING_CORE,
                )
            )
        if record.currency is not None:
            facts.append(
                VerifiedFact(
                    fact="transaction_currency",
                    value=record.currency,
                    source=FactSource.BANKING_CORE,
                )
            )
        facts.append(
            VerifiedFact(
                fact="transaction_date",
                value=record.transaction_date.isoformat() if record.transaction_date else None,
                source=FactSource.BANKING_CORE,
            )
        )
        facts.append(
            VerifiedFact(
                fact="process_date",
                value=record.process_date.isoformat() if record.process_date else None,
                source=FactSource.BANKING_CORE,
            )
        )
    return tuple(facts)


def _evidence(record: TransactionRecord | None) -> tuple[Evidence, ...]:
    if record is None:
        return ()
    evidence: list[Evidence] = []
    if record.response_code:
        # Verbatim: the curated contract documents no meaning for this code, so none is attached.
        evidence.append(Evidence(kind="transaction_response_code", value=record.response_code))
    if record.amount_usd is not None:
        evidence.append(Evidence(kind="transaction_amount_usd", value=_amount(record.amount_usd)))
    if record.process_date is not None:
        evidence.append(
            Evidence(kind="transaction_process_date", value=record.process_date.isoformat())
        )
    return tuple(evidence)


def build_handoff(
    *,
    incident_id: str,
    case_id: str,
    request: IncidentSummary,
    decision: PolicyDecision,
    session_valid: bool,
    record: TransactionRecord | None,
    actions: tuple[WorkflowAction, ...],
) -> Handoff:
    unavailable = decision.reason_code in (
        PolicyReasonCode.TOOL_FAILURE_EXHAUSTED,
        PolicyReasonCode.REQUIRED_EVIDENCE_MISSING,
    )
    return Handoff(
        case_id=case_id,
        incident_id=incident_id,
        customer_request=request,
        verified_facts=_verified_facts(session_valid, record, unavailable),
        actions_taken=actions,
        supporting_evidence=_evidence(record),
        unresolved_questions=UNRESOLVED_BY_REASON.get(decision.reason_code, ()),
        policy_decision=decision,
        recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
    )

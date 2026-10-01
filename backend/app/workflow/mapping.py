"""The single mapping point from verified workflow state to PolicyContext.

Security-critical: every PolicyContext field is derived here and nowhere else. The state carries
only what the workflow actually observed, and its invariants make a failed banking read
structurally unable to produce a candidate or a transaction status, so no such failure can ever
reach the Policy Engine as a resolvable incident.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.banking.models import TransactionRecord
from app.policy import PolicyContext


@dataclass(frozen=True, slots=True)
class VerifiedWorkflowState:
    """Observed workflow state before any policy interpretation.

    Every field is required, so the orchestrator has to state each one. `verified_transaction` is
    the single carrier of transaction status: there is no separate status field a caller or a
    lookup could fill in.
    """

    session_valid: bool
    authorized: bool
    in_scope: bool
    authenticated_customer_id: str | None
    candidate_transaction_count: int
    verified_transaction: TransactionRecord | None
    approved_with_unresolved_issue: bool
    tool_failure_exhausted: bool
    required_evidence_missing: bool

    def __post_init__(self) -> None:
        if self.candidate_transaction_count < 0:
            raise ValueError("candidate_transaction_count cannot be negative")
        if self.session_valid and not self.authenticated_customer_id:
            raise ValueError("a valid session carries the authenticated customer")
        if self.tool_failure_exhausted and (
            self.candidate_transaction_count > 0 or self.verified_transaction is not None
        ):
            raise ValueError(
                "a failed banking read cannot produce candidates or a verified transaction"
            )
        if self.verified_transaction is not None:
            if self.candidate_transaction_count != 1:
                raise ValueError("a verified transaction requires exactly one candidate")
            if self.verified_transaction.customer_id != self.authenticated_customer_id:
                raise ValueError("verified transaction is not owned by the authenticated customer")


def to_policy_context(state: VerifiedWorkflowState) -> PolicyContext:
    record = state.verified_transaction
    return PolicyContext(
        session_valid=state.session_valid,
        authorized=state.authorized,
        in_scope=state.in_scope,
        tool_failure_exhausted=state.tool_failure_exhausted,
        required_evidence_missing=state.required_evidence_missing,
        candidate_transaction_count=state.candidate_transaction_count,
        # A status exists only because the Banking Core returned a transaction owned by the
        # authenticated customer; nothing else can supply one.
        transaction_status=record.transaction_status if record is not None else None,
        approved_with_unresolved_issue=state.approved_with_unresolved_issue,
    )

"""Synthetic Banking Policy v1 (v1.0.0) deterministic policy engine.

Hackathon demonstration model, not a real bank, organizer, settlement, or regulatory policy.
Deterministic: identical inputs yield identical outputs. No LLM, no randomness.

Precedence (highest → lowest):
1. Safety / authorization / unsupported scope (A, B)
2. Tool or required-evidence failure (C, E)
3. Transaction identification (D) — zero or multiple candidates
4. Verified transaction status (F,G,H,I,J,K)

Synthetic assumptions (explicit):
- Declined → RESOLVE at verified status level only; no cause inference.
- Pending → ESCALATE; no settlement SLA invented.
- Reversed → ESCALATE; status != verified funds returned.
- Approved + unresolved reported issue → ESCALATE.
- Approved without supported incident → ABSTAIN (no supported incident requires action).
- Unknown/unexpected status → ESCALATE. Session, authorization, scope, evidence and transaction
  identity are already verified, so the incident is real and in scope; only the policy is unable to
  support the status. That is an automation boundary requiring human review, not an out-of-scope
  request, so the status is never remapped to a known one.
"""

from __future__ import annotations

from app.policy.models import (
    POLICY_VERSION,
    PolicyContext,
    PolicyDecision,
    PolicyOutcome,
    PolicyReasonCode,
    PolicyRule,
)


def _decide(
    outcome: PolicyOutcome,
    reason: PolicyReasonCode,
    rule: PolicyRule,
) -> PolicyDecision:
    return PolicyDecision(
        outcome=outcome,
        reason_code=reason,
        policy_rule=rule,
        policy_version=POLICY_VERSION,
    )


def evaluate_policy(context: PolicyContext) -> PolicyDecision:
    """Evaluate policy. Pure function with no side effects."""

    # A. Safety
    if not context.session_valid:
        return _decide(
            PolicyOutcome.ABSTAIN,
            PolicyReasonCode.INVALID_SESSION,
            PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW,
        )
    if not context.authorized:
        return _decide(
            PolicyOutcome.ABSTAIN,
            PolicyReasonCode.UNAUTHORIZED,
            PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW,
        )

    # B. Scope
    if not context.in_scope:
        return _decide(
            PolicyOutcome.ABSTAIN,
            PolicyReasonCode.OUT_OF_SCOPE,
            PolicyRule.B_OUT_OF_SCOPE,
        )

    # C. Tool failure
    if context.tool_failure_exhausted:
        return _decide(
            PolicyOutcome.ESCALATE,
            PolicyReasonCode.TOOL_FAILURE_EXHAUSTED,
            PolicyRule.C_TOOL_FAILURE,
        )

    # E. Required evidence
    if context.required_evidence_missing:
        return _decide(
            PolicyOutcome.ESCALATE,
            PolicyReasonCode.REQUIRED_EVIDENCE_MISSING,
            PolicyRule.E_REQUIRED_EVIDENCE_MISSING,
        )

    # D. Identification
    if context.candidate_transaction_count > 1:
        return _decide(
            PolicyOutcome.CLARIFY,
            PolicyReasonCode.MULTIPLE_CANDIDATE_TRANSACTIONS,
            PolicyRule.D_MULTIPLE_CANDIDATES,
        )
    if context.candidate_transaction_count == 0:
        return _decide(
            PolicyOutcome.CLARIFY,
            PolicyReasonCode.NO_MATCHING_TRANSACTION,
            PolicyRule.D_NO_CANDIDATES,
        )

    # Exactly one candidate identified; proceed to status rules.
    status = (context.transaction_status or "").strip()

    if status == "Declined":
        # RESOLVE authorizes the grounded status-level answer "the transaction is verified as
        # Declined". A missing verified decline cause does not imply the customer must confirm
        # anything: no confirmation-gated action is authorized anywhere in this policy version.
        return _decide(
            PolicyOutcome.RESOLVE,
            PolicyReasonCode.DECLINED_STATUS,
            PolicyRule.F_DECLINED,
        )
    if status == "Pending":
        return _decide(
            PolicyOutcome.ESCALATE,
            PolicyReasonCode.PENDING_STATUS,
            PolicyRule.G_PENDING,
        )
    if status == "Reversed":
        return _decide(
            PolicyOutcome.ESCALATE,
            PolicyReasonCode.REVERSED_STATUS,
            PolicyRule.H_REVERSED,
        )
    if status == "Approved":
        if context.approved_with_unresolved_issue:
            return _decide(
                PolicyOutcome.ESCALATE,
                PolicyReasonCode.APPROVED_UNRESOLVED_ISSUE,
                PolicyRule.I_APPROVED_UNRESOLVED,
            )
        return _decide(
            PolicyOutcome.ABSTAIN,
            PolicyReasonCode.APPROVED_NO_SUPPORTED_INCIDENT,
            PolicyRule.J_APPROVED_NO_INCIDENT,
        )

    # K. Verified incident, unsupported status: escalate for human review. Reached only after
    # session, authorization, scope, evidence and transaction identity all verified.
    return _decide(
        PolicyOutcome.ESCALATE,
        PolicyReasonCode.UNKNOWN_TRANSACTION_STATUS,
        PolicyRule.K_UNKNOWN_STATUS,
    )

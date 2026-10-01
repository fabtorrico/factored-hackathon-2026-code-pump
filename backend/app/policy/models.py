"""Typed policy input and output for Synthetic Banking Policy v1.

Hackathon demonstration model. Not a real bank, organizer, settlement, or regulatory policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Literal

POLICY_VERSION: Literal["1.0.0"] = "1.0.0"


@unique
class PolicyOutcome(StrEnum):
    """What the workflow is permitted to do next.

    RESOLVE: a verified incident can be resolved automatically within policy.
    CLARIFY: additional customer/workflow information is needed before the correct subject of the
    incident can be identified.
    ESCALATE: the incident is valid and in scope, but automated resolution cannot proceed safely
    or confidently, so it is routed to human review.
    ABSTAIN: the system must not act because the request or state is unauthorized, invalid,
    unsupported in scope, or carries no supported incident action.
    """

    RESOLVE = "RESOLVE"
    CLARIFY = "CLARIFY"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"


@unique
class PolicyReasonCode(StrEnum):
    INVALID_SESSION = "invalid_session"
    UNAUTHORIZED = "unauthorized"
    OUT_OF_SCOPE = "out_of_scope"
    TOOL_FAILURE_EXHAUSTED = "tool_failure_exhausted"
    REQUIRED_EVIDENCE_MISSING = "required_evidence_missing"
    NO_MATCHING_TRANSACTION = "no_matching_transaction"
    MULTIPLE_CANDIDATE_TRANSACTIONS = "multiple_candidate_transactions"
    DECLINED_STATUS = "declined_status"
    PENDING_STATUS = "pending_status"
    REVERSED_STATUS = "reversed_status"
    APPROVED_UNRESOLVED_ISSUE = "approved_unresolved_issue"
    APPROVED_NO_SUPPORTED_INCIDENT = "approved_no_supported_incident"
    # Reached only once session, authorization, scope, evidence and transaction identity are all
    # verified: the status itself is unsupported by policy, so the case needs human review.
    UNKNOWN_TRANSACTION_STATUS = "unknown_transaction_status"


@unique
class PolicyRule(StrEnum):
    A_INVALID_UNAUTHORIZED_WORKFLOW = "A_INVALID_UNAUTHORIZED_WORKFLOW"
    B_OUT_OF_SCOPE = "B_OUT_OF_SCOPE"
    C_TOOL_FAILURE = "C_TOOL_FAILURE"
    D_NO_CANDIDATES = "D_NO_CANDIDATES"
    D_MULTIPLE_CANDIDATES = "D_MULTIPLE_CANDIDATES"
    E_REQUIRED_EVIDENCE_MISSING = "E_REQUIRED_EVIDENCE_MISSING"
    F_DECLINED = "F_DECLINED"
    G_PENDING = "G_PENDING"
    H_REVERSED = "H_REVERSED"
    I_APPROVED_UNRESOLVED = "I_APPROVED_UNRESOLVED"
    J_APPROVED_NO_INCIDENT = "J_APPROVED_NO_INCIDENT"
    K_UNKNOWN_STATUS = "K_UNKNOWN_STATUS"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Outcome of one evaluation: what to do, why, and under which pinned rule.

    No Phase 3A rule authorizes an action requiring explicit customer confirmation, so the concept
    is absent. RESOLVE authorizes at most a grounded status-level answer, never money movement or
    another sensitive action.
    """

    outcome: PolicyOutcome
    reason_code: PolicyReasonCode
    policy_rule: PolicyRule
    policy_version: Literal["1.0.0"] = POLICY_VERSION


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Verified facts and explicit workflow state.

    Optional evidence (response_code, amount_usd, current_balance) is deliberately absent: it is
    recorded by the Banking Core and can be displayed later, but no Phase 3A rule reads it, so it
    cannot influence a decision. Raw customer prose and PII are out of scope by construction.
    """

    session_valid: bool = True
    authorized: bool = True
    in_scope: bool = True
    tool_failure_exhausted: bool = False
    required_evidence_missing: bool = False
    candidate_transaction_count: int = 0
    transaction_status: str | None = None
    approved_with_unresolved_issue: bool = False

    def __post_init__(self) -> None:
        if self.candidate_transaction_count < 0:
            raise ValueError("candidate_transaction_count cannot be negative")

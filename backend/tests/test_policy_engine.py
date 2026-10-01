"""Decision-table tests for Synthetic Banking Policy v1.

All inputs are synthetic. No organizer data, no Banking Core, no database.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from app.data.contracts import TRANSACTION_STATUS_DOMAIN
from app.policy import (
    POLICY_VERSION,
    PolicyContext,
    PolicyDecision,
    PolicyOutcome,
    PolicyReasonCode,
    PolicyRule,
    evaluate_policy,
)


def _identified(status: str | None, **overrides: object) -> PolicyContext:
    """One uniquely identified candidate with a verified status."""
    return PolicyContext(
        candidate_transaction_count=1,
        transaction_status=status,
        **overrides,  # type: ignore[arg-type]
    )


def test_policy_version_is_pinned() -> None:
    assert POLICY_VERSION == "1.0.0"


def test_every_decision_carries_version_rule_and_reason() -> None:
    decision = evaluate_policy(_identified("Declined"))
    assert decision.policy_version == POLICY_VERSION
    assert isinstance(decision.policy_rule, PolicyRule)
    assert isinstance(decision.reason_code, PolicyReasonCode)


# --- A. Safety ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"session_valid": False}, PolicyReasonCode.INVALID_SESSION),
        ({"authorized": False}, PolicyReasonCode.UNAUTHORIZED),
    ],
)
def test_invalid_workflow_state_abstains(
    overrides: dict[str, bool], reason: PolicyReasonCode
) -> None:
    decision = evaluate_policy(_identified("Declined", **overrides))
    assert decision.outcome is PolicyOutcome.ABSTAIN
    assert decision.reason_code is reason
    assert decision.policy_rule is PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW


def test_invalid_session_takes_precedence_over_unauthorized() -> None:
    decision = evaluate_policy(_identified("Declined", session_valid=False, authorized=False))
    assert decision.reason_code is PolicyReasonCode.INVALID_SESSION


# --- B. Scope ----------------------------------------------------------------------


def test_out_of_scope_abstains() -> None:
    decision = evaluate_policy(_identified("Declined", in_scope=False))
    assert decision.outcome is PolicyOutcome.ABSTAIN
    assert decision.reason_code is PolicyReasonCode.OUT_OF_SCOPE
    assert decision.policy_rule is PolicyRule.B_OUT_OF_SCOPE


# --- C. Tool failure ---------------------------------------------------------------


def test_exhausted_tool_failure_escalates() -> None:
    decision = evaluate_policy(_identified("Declined", tool_failure_exhausted=True))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.TOOL_FAILURE_EXHAUSTED
    assert decision.policy_rule is PolicyRule.C_TOOL_FAILURE


# --- E. Required evidence ----------------------------------------------------------


def test_missing_required_evidence_escalates() -> None:
    decision = evaluate_policy(_identified("Declined", required_evidence_missing=True))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.REQUIRED_EVIDENCE_MISSING


# --- D. Identification -------------------------------------------------------------


def test_zero_candidates_clarifies() -> None:
    decision = evaluate_policy(PolicyContext(candidate_transaction_count=0))
    assert decision.outcome is PolicyOutcome.CLARIFY
    assert decision.reason_code is PolicyReasonCode.NO_MATCHING_TRANSACTION
    assert decision.policy_rule is PolicyRule.D_NO_CANDIDATES


def test_multiple_candidates_clarifies() -> None:
    decision = evaluate_policy(
        PolicyContext(candidate_transaction_count=3, transaction_status="Declined")
    )
    assert decision.outcome is PolicyOutcome.CLARIFY
    assert decision.reason_code is PolicyReasonCode.MULTIPLE_CANDIDATE_TRANSACTIONS
    assert decision.policy_rule is PolicyRule.D_MULTIPLE_CANDIDATES


def test_exactly_one_candidate_proceeds_to_status_rules() -> None:
    assert evaluate_policy(_identified("Declined")).outcome is PolicyOutcome.RESOLVE


def test_negative_candidate_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        PolicyContext(candidate_transaction_count=-1)


# --- F. Declined -------------------------------------------------------------------


def test_declined_resolves_at_status_level() -> None:
    decision = evaluate_policy(_identified("Declined"))
    assert decision.outcome is PolicyOutcome.RESOLVE
    assert decision.reason_code is PolicyReasonCode.DECLINED_STATUS
    assert decision.policy_rule is PolicyRule.F_DECLINED
    # No customer confirmation is required for any action in Phase 3A: RESOLVE means only
    # "the transaction is verified as Declined" at status level.
    assert not hasattr(decision, "customer_confirmation_required")


@pytest.mark.parametrize("status", sorted(TRANSACTION_STATUS_DOMAIN))
def test_status_domain_is_covered(status: str) -> None:
    assert evaluate_policy(_identified(status)).outcome in set(PolicyOutcome)


def test_declined_ignores_optional_evidence() -> None:
    # response_code, amount_usd and current_balance are not part of PolicyContext, so a null
    # optional field cannot block or alter a status-level resolution.
    decision = evaluate_policy(_identified("Declined"))
    assert decision.outcome is PolicyOutcome.RESOLVE
    assert decision.reason_code is PolicyReasonCode.DECLINED_STATUS


def test_declined_does_not_interpret_response_code() -> None:
    for code in ("00", "54", "14", "05", "51"):
        assert evaluate_policy(_identified("Declined")).reason_code is (
            PolicyReasonCode.DECLINED_STATUS
        )
        assert code  # observed values are never inputs to policy


# --- G. Pending --------------------------------------------------------------------


def test_pending_escalates() -> None:
    decision = evaluate_policy(_identified("Pending"))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.PENDING_STATUS
    assert decision.policy_rule is PolicyRule.G_PENDING


# --- H. Reversed -------------------------------------------------------------------


def test_reversed_escalates() -> None:
    decision = evaluate_policy(_identified("Reversed"))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.REVERSED_STATUS
    assert decision.policy_rule is PolicyRule.H_REVERSED


# --- I/J. Approved -----------------------------------------------------------------


def test_approved_with_unresolved_issue_escalates() -> None:
    decision = evaluate_policy(_identified("Approved", approved_with_unresolved_issue=True))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.APPROVED_UNRESOLVED_ISSUE
    assert decision.policy_rule is PolicyRule.I_APPROVED_UNRESOLVED


def test_approved_without_incident_abstains() -> None:
    decision = evaluate_policy(_identified("Approved"))
    assert decision.outcome is PolicyOutcome.ABSTAIN
    assert decision.reason_code is PolicyReasonCode.APPROVED_NO_SUPPORTED_INCIDENT
    assert decision.policy_rule is PolicyRule.J_APPROVED_NO_INCIDENT


# --- K. Unknown status -------------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["", "   ", None, "Completed", "declined", "SETTLED", "Blocked", "unknown"]
)
def test_unknown_status_escalates(status: str | None) -> None:
    decision = evaluate_policy(_identified(status))
    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason_code is PolicyReasonCode.UNKNOWN_TRANSACTION_STATUS
    assert decision.policy_rule is PolicyRule.K_UNKNOWN_STATUS


@pytest.mark.parametrize(
    "status", ["", "   ", None, "Completed", "declined", "SETTLED", "Blocked", "unknown"]
)
def test_unknown_status_is_not_mapped_to_a_known_status(status: str | None) -> None:
    known = {
        PolicyReasonCode.DECLINED_STATUS,
        PolicyReasonCode.PENDING_STATUS,
        PolicyReasonCode.REVERSED_STATUS,
        PolicyReasonCode.APPROVED_UNRESOLVED_ISSUE,
        PolicyReasonCode.APPROVED_NO_SUPPORTED_INCIDENT,
    }
    assert evaluate_policy(_identified(status)).reason_code not in known


def test_unknown_status_still_abstains_before_identification() -> None:
    # An unsupported status only escalates once an incident is identified; without one there is
    # no verified in-scope incident, so CLARIFY remains correct.
    decision = evaluate_policy(PolicyContext(candidate_transaction_count=0))
    assert decision.outcome is PolicyOutcome.CLARIFY
    assert decision.policy_rule is PolicyRule.D_NO_CANDIDATES


def test_engine_handles_every_status_in_the_data_domain() -> None:
    handled = {
        evaluate_policy(_identified(status)).policy_rule for status in TRANSACTION_STATUS_DOMAIN
    }
    assert PolicyRule.K_UNKNOWN_STATUS not in handled


# --- Precedence --------------------------------------------------------------------


def test_unauthorized_beats_declined() -> None:
    decision = evaluate_policy(_identified("Declined", authorized=False))
    assert decision.outcome is PolicyOutcome.ABSTAIN
    assert decision.policy_rule is PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW


def test_out_of_scope_beats_declined() -> None:
    decision = evaluate_policy(_identified("Declined", in_scope=False))
    assert decision.outcome is PolicyOutcome.ABSTAIN
    assert decision.policy_rule is PolicyRule.B_OUT_OF_SCOPE


def test_scope_beats_tool_failure() -> None:
    decision = evaluate_policy(_identified("Declined", in_scope=False, tool_failure_exhausted=True))
    assert decision.policy_rule is PolicyRule.B_OUT_OF_SCOPE


def test_ambiguity_beats_status() -> None:
    decision = evaluate_policy(
        PolicyContext(
            candidate_transaction_count=2,
            transaction_status="Declined",
            required_evidence_missing=False,
        )
    )
    assert decision.outcome is PolicyOutcome.CLARIFY
    assert decision.policy_rule is PolicyRule.D_MULTIPLE_CANDIDATES


def test_failure_beats_ambiguity_and_status() -> None:
    decision = evaluate_policy(
        PolicyContext(
            candidate_transaction_count=4,
            transaction_status="Declined",
            tool_failure_exhausted=True,
        )
    )
    assert decision.policy_rule is PolicyRule.C_TOOL_FAILURE


def test_missing_evidence_beats_identifiable_status() -> None:
    decision = evaluate_policy(_identified("Declined", required_evidence_missing=True))
    assert decision.policy_rule is PolicyRule.E_REQUIRED_EVIDENCE_MISSING


def test_every_precedence_level_is_attainable() -> None:
    # Guards against a level becoming unreachable and silently untested.
    rules = {
        evaluate_policy(_identified("Declined", authorized=False)).policy_rule,
        evaluate_policy(_identified("Declined", in_scope=False)).policy_rule,
        evaluate_policy(_identified("Declined", tool_failure_exhausted=True)).policy_rule,
        evaluate_policy(_identified("Declined", required_evidence_missing=True)).policy_rule,
        evaluate_policy(PolicyContext(candidate_transaction_count=0)).policy_rule,
        evaluate_policy(_identified("Declined")).policy_rule,
    }
    assert rules == {
        PolicyRule.A_INVALID_UNAUTHORIZED_WORKFLOW,
        PolicyRule.B_OUT_OF_SCOPE,
        PolicyRule.C_TOOL_FAILURE,
        PolicyRule.E_REQUIRED_EVIDENCE_MISSING,
        PolicyRule.D_NO_CANDIDATES,
        PolicyRule.F_DECLINED,
    }


# --- Determinism -------------------------------------------------------------------


@pytest.mark.parametrize(
    "context",
    [
        _identified("Declined"),
        _identified("Pending"),
        _identified("Reversed"),
        _identified("Approved", approved_with_unresolved_issue=True),
        _identified("Completed"),
        PolicyContext(candidate_transaction_count=2),
        _identified("Declined", tool_failure_exhausted=True),
    ],
)
def test_evaluation_is_deterministic(context: PolicyContext) -> None:
    assert evaluate_policy(context) == evaluate_policy(context)


def test_policy_decision_carries_only_outcome_reason_rule_and_version() -> None:
    assert tuple(f.name for f in fields(PolicyDecision)) == (
        "outcome",
        "reason_code",
        "policy_rule",
        "policy_version",
    )


def test_decision_is_immutable() -> None:
    decision = evaluate_policy(_identified("Declined"))
    with pytest.raises(AttributeError):
        decision.outcome = PolicyOutcome.ABSTAIN  # type: ignore[misc]


def test_default_context_clarifies() -> None:
    decision = evaluate_policy(PolicyContext())
    assert decision.outcome is PolicyOutcome.CLARIFY
    assert decision.reason_code is PolicyReasonCode.NO_MATCHING_TRANSACTION

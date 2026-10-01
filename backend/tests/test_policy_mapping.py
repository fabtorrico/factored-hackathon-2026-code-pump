"""The verified state to PolicyContext mapping, and the invariants that protect it.

These tests pin the single security-critical boundary in Phase 3B: transaction status can only
exist in a `PolicyContext` because the Banking Core returned an owned record, and a failed read can
never produce a candidate, a status or a resolvable incident.
"""

import dataclasses

import pytest
from conftest import OTHER, OWNER

from app.banking.models import TransactionRecord
from app.policy import PolicyContext, PolicyOutcome, evaluate_policy
from app.workflow.mapping import VerifiedWorkflowState, to_policy_context

MOMENT_RECORD = TransactionRecord(
    transaction_id="TXN-003",
    customer_id=OWNER,
    transaction_status="Pending",
    transaction_type="Transfer",
    amount=1750.0,
    currency="USD",
    transaction_date="2026-06-17T14:30:00+00:00",
    process_date="2026-06-17T15:00:00+00:00",
)


def _state(**overrides) -> VerifiedWorkflowState:
    fields = {
        "session_valid": True,
        "authorized": True,
        "in_scope": True,
        "authenticated_customer_id": OWNER,
        "candidate_transaction_count": 1,
        "verified_transaction": MOMENT_RECORD,
        "approved_with_unresolved_issue": False,
        "tool_failure_exhausted": False,
        "required_evidence_missing": False,
    }
    fields.update(overrides)
    return VerifiedWorkflowState(**fields)


def _context(**overrides) -> PolicyContext:
    return to_policy_context(_state(**overrides))


# --- Direct mapping --------------------------------------------------------------------


def test_every_policy_field_comes_from_the_verified_state() -> None:
    context = _context(approved_with_unresolved_issue=True)

    assert context == PolicyContext(
        session_valid=True,
        authorized=True,
        in_scope=True,
        candidate_transaction_count=1,
        transaction_status="Pending",
        approved_with_unresolved_issue=True,
        tool_failure_exhausted=False,
        required_evidence_missing=False,
    )


def test_status_exists_only_because_a_record_was_returned() -> None:
    empty = _context(verified_transaction=None, candidate_transaction_count=0)

    assert _context().transaction_status == "Pending"
    assert empty.transaction_status is None


def test_customer_identity_is_not_part_of_the_policy_context() -> None:
    # Identity decides authorization inside the Banking Core and never travels into the policy.
    assert not hasattr(_context(), "authenticated_customer_id")
    assert "customer" not in {field.name for field in dataclasses.fields(PolicyContext)}


def test_no_caller_supplied_status_survives_the_mapping() -> None:
    # There is no parameter to smuggle a status through: the only source is the record.
    with pytest.raises(TypeError):
        VerifiedWorkflowState(
            session_valid=True,
            authorized=True,
            in_scope=True,
            authenticated_customer_id=OWNER,
            candidate_transaction_count=1,
            verified_transaction=MOMENT_RECORD,
            approved_with_unresolved_issue=False,
            tool_failure_exhausted=False,
            required_evidence_missing=False,
            transaction_status="Approved",
        )


# --- Failed read invariants -------------------------------------------------------------


def test_a_failed_read_cannot_carry_a_candidate() -> None:
    with pytest.raises(ValueError, match="cannot produce candidates"):
        _state(tool_failure_exhausted=True, verified_transaction=None)


def test_a_failed_read_cannot_carry_a_verified_transaction() -> None:
    with pytest.raises(ValueError, match="cannot produce candidates"):
        _state(tool_failure_exhausted=True)


def test_a_failed_read_can_never_resolve() -> None:
    decision = evaluate_policy(
        _context(
            tool_failure_exhausted=True,
            verified_transaction=None,
            candidate_transaction_count=0,
        )
    )

    assert decision.outcome is PolicyOutcome.ESCALATE


def test_a_failed_read_exposes_no_status_to_the_policy() -> None:
    context = _context(
        tool_failure_exhausted=True, verified_transaction=None, candidate_transaction_count=0
    )

    assert context.transaction_status is None
    assert context.candidate_transaction_count == 0


# --- Ownership and shape invariants ------------------------------------------------------


def test_a_verified_transaction_must_be_owned_by_the_authenticated_customer() -> None:
    with pytest.raises(ValueError, match="not owned by the authenticated customer"):
        _context(verified_transaction=MOMENT_RECORD.model_copy(update={"customer_id": OTHER}))


def test_a_verified_transaction_requires_exactly_one_candidate() -> None:
    with pytest.raises(ValueError, match="exactly one candidate"):
        _context(candidate_transaction_count=2)
    with pytest.raises(ValueError, match="exactly one candidate"):
        _context(candidate_transaction_count=0)


def test_a_valid_session_must_carry_its_customer() -> None:
    with pytest.raises(ValueError, match="valid session carries the authenticated customer"):
        _context(authenticated_customer_id=None)


def test_a_negative_candidate_count_is_impossible() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        _state(verified_transaction=None, candidate_transaction_count=-1)


def test_an_unusable_session_can_carry_no_customer_and_no_candidates() -> None:
    state = _state(
        session_valid=False,
        authorized=False,
        authenticated_customer_id=None,
        verified_transaction=None,
        candidate_transaction_count=0,
    )

    decision = evaluate_policy(to_policy_context(state))

    assert decision.outcome is PolicyOutcome.ABSTAIN


def test_verified_state_is_immutable() -> None:
    state = _state()

    with pytest.raises(AttributeError):
        state.session_valid = False

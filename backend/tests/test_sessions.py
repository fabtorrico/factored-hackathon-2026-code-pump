from datetime import timedelta

import pytest
from conftest import OTHER, OWNER, SESSION_TTL

from app.banking.errors import (
    ExpiredSessionError,
    InvalidRequestError,
    InvalidSessionError,
    Reason,
)
from app.banking.sessions import SessionStore

SHORT_TTL = timedelta(minutes=5)


def test_issued_session_carries_an_opaque_id_and_one_customer(sessions: SessionStore) -> None:
    session = sessions.issue(OWNER)

    assert session.customer_id == OWNER
    assert len(session.session_id) >= 32
    assert OWNER not in session.session_id
    assert session.expires_at - session.issued_at == SESSION_TTL


def test_active_session_resolves(sessions: SessionStore) -> None:
    assert sessions.resolve(sessions.issue(OWNER).session_id).customer_id == OWNER


def test_unknown_session_is_rejected(sessions: SessionStore) -> None:
    with pytest.raises(InvalidSessionError) as denied:
        sessions.resolve("not-a-real-session")

    assert denied.value.reason is Reason.INVALID_SESSION
    assert denied.value.customer_id is None


@pytest.mark.parametrize("presented", [None, "", "   "])
def test_absent_session_is_rejected(sessions: SessionStore, presented: str | None) -> None:
    with pytest.raises(InvalidSessionError):
        sessions.resolve(presented)


def test_expired_session_is_rejected(sessions: SessionStore, clock) -> None:
    session = sessions.issue(OWNER, ttl=SHORT_TTL)

    clock.advance(SHORT_TTL)

    with pytest.raises(ExpiredSessionError) as expired:
        sessions.resolve(session.session_id)

    assert expired.value.reason is Reason.EXPIRED_SESSION
    assert expired.value.customer_id == OWNER


def test_session_is_valid_up_to_its_expiry_instant(sessions: SessionStore, clock) -> None:
    session = sessions.issue(OWNER, ttl=SHORT_TTL)

    clock.advance(SHORT_TTL - timedelta(seconds=1))

    assert sessions.resolve(session.session_id).customer_id == OWNER


def test_revoked_session_is_rejected(sessions: SessionStore) -> None:
    session = sessions.issue(OWNER)

    sessions.revoke(session.session_id)

    with pytest.raises(InvalidSessionError):
        sessions.resolve(session.session_id)


def test_two_sessions_keep_their_own_customer(sessions: SessionStore) -> None:
    first = sessions.issue(OWNER)
    second = sessions.issue(OTHER)

    assert first.session_id != second.session_id
    assert sessions.resolve(first.session_id).customer_id == OWNER
    assert sessions.resolve(second.session_id).customer_id == OTHER


def test_blank_customer_cannot_open_a_session(sessions: SessionStore) -> None:
    with pytest.raises(InvalidRequestError) as invalid:
        sessions.issue("   ")

    assert invalid.value.reason is Reason.INVALID_REQUEST

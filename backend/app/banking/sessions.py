from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Lock

from app.banking.errors import ExpiredSessionError, InvalidRequestError, InvalidSessionError

Clock = Callable[[], datetime]
SESSION_ID_BYTES = 32


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Session:
    """A trusted demo identity: exactly one session id, exactly one customer.

    The session id is an opaque bearer credential. Its value never appears in an audit event.
    """

    session_id: str
    customer_id: str
    issued_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


class SessionStore:
    """In-process session registry for the prototype.

    Issuance is trusted by design: a demo caller asserts who it is and receives a session. There
    is no credential verification, refresh, persistence or external identity provider here, and
    none is in scope for this phase. What matters downstream is only that every banking tool
    resolves its customer from a session and never from caller-supplied input.
    """

    def __init__(self, ttl: timedelta = timedelta(minutes=30), clock: Clock | None = None) -> None:
        self._ttl = ttl
        self._clock: Clock = clock or _utc_now
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    def issue(self, customer_id: str, *, ttl: timedelta | None = None) -> Session:
        customer = customer_id.strip()
        if not customer:
            raise InvalidRequestError("customer_id is required to open a session")
        now = self._clock()
        session = Session(
            session_id=token_urlsafe(SESSION_ID_BYTES),
            customer_id=customer,
            issued_at=now,
            expires_at=now + (ttl or self._ttl),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def resolve(self, session_id: str | None) -> Session:
        key = (session_id or "").strip()
        with self._lock:
            session = self._sessions.get(key)
        if session is None:
            raise InvalidSessionError("no session matches the presented identifier")
        if session.is_expired(self._clock()):
            raise ExpiredSessionError(
                f"session expired at {session.expires_at.isoformat()}",
                customer_id=session.customer_id,
            )
        return session

    def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop((session_id or "").strip(), None)

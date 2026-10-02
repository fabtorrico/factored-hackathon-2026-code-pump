"""Demo-only agent access.

A deliberately separate, in-process credential from the customer SessionStore. It exists so the
agent workspace is not reachable with a customer session and a customer cannot inherit agent access
by opening one. It is not production workforce authentication: no password, role, permission or
external identity provider is in scope, and every agent sees the same read-only queue.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import Lock

from app.banking.errors import ExpiredSessionError, InvalidSessionError

Clock = Callable[[], datetime]
AGENT_SESSION_ID_BYTES = 32
DEFAULT_AGENT_DISPLAY_NAME = "Demo specialist"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AgentSession:
    """One demo agent's read-only session. The identifier is never rendered or logged."""

    agent_session_id: str
    display_name: str
    issued_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


class AgentSessionStore:
    def __init__(self, ttl: timedelta = timedelta(minutes=30), clock: Clock | None = None) -> None:
        self._ttl = ttl
        self._clock: Clock = clock or _utc_now
        self._sessions: dict[str, AgentSession] = {}
        self._lock = Lock()

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    def issue(self, display_name: str = DEFAULT_AGENT_DISPLAY_NAME) -> AgentSession:
        now = self._clock()
        session = AgentSession(
            agent_session_id=token_urlsafe(AGENT_SESSION_ID_BYTES),
            display_name=display_name,
            issued_at=now,
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._sessions[session.agent_session_id] = session
        return session

    def resolve(self, agent_session_id: str | None) -> AgentSession:
        key = (agent_session_id or "").strip()
        with self._lock:
            session = self._sessions.get(key)
        if session is None:
            raise InvalidSessionError("no agent session matches the presented identifier")
        if session.is_expired(self._clock()):
            raise ExpiredSessionError(f"agent session expired at {session.expires_at.isoformat()}")
        return session

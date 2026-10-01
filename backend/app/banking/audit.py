import hashlib
from collections import deque
from datetime import datetime
from threading import Lock
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.banking.errors import Outcome, Reason

FINGERPRINT_LENGTH = 12


def fingerprint(session_id: str | None) -> str | None:
    """Stable, non-reversible handle for a session id.

    The session id is a bearer credential, so audit events store only this digest of it.
    """
    if not session_id:
        return None
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


class AuditEvent(BaseModel):
    """One executed banking tool call.

    Deliberately narrow: no chain-of-thought, no prompts, no request bodies, no customer records
    and no raw values beyond the identifiers needed to reconstruct who asked for what.
    """

    model_config = ConfigDict(frozen=True)

    occurred_at: datetime
    tool: str
    outcome: Outcome
    reason: Reason | None = None
    customer_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    latency_ms: float
    session_fingerprint: str | None = None


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...

    def recent(self, limit: int = 50) -> list[AuditEvent]: ...


class InMemoryAuditSink:
    """Bounded in-process audit buffer. Operational audit persistence is a later phase."""

    def __init__(self, capacity: int = 500) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=capacity)
        self._lock = Lock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def recent(self, limit: int = 50) -> list[AuditEvent]:
        with self._lock:
            events = list(self._events)
        return events[-limit:][::-1]

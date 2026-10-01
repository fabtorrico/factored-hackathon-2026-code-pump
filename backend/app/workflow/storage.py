"""Local SQLite store for application-generated operational state.

The curated DuckDB database stays the source of banking facts and nothing is copied from it into
SQLite. Standard library `sqlite3` only, no ORM. Initialization is deterministic and idempotent:
the same DDL every time, `CREATE TABLE IF NOT EXISTS` for every table.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.policy import PolicyOutcome, PolicyReasonCode, PolicyRule
from app.workflow.models import (
    CaseStatus,
    Incident,
    SupportCase,
    SupportRoute,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id    TEXT PRIMARY KEY,
    customer_id    TEXT,
    created_at     TEXT NOT NULL,
    status         TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    reason_code    TEXT NOT NULL,
    policy_rule    TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    transaction_id TEXT
);

CREATE TABLE IF NOT EXISTS support_cases (
    case_id           TEXT PRIMARY KEY,
    incident_id       TEXT NOT NULL REFERENCES incidents (incident_id),
    status            TEXT NOT NULL,
    recommended_route TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_events (
    sequence    INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    detail      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS workflow_events_incident ON workflow_events (incident_id, sequence);
"""


class OperationalStoreError(RuntimeError):
    """An operational write, or the read back that verifies it, failed.

    Raised instead of letting a driver error escape, so a caller that must verify its own write can
    turn an unverifiable action into a reported failure.
    """


def _stamp(moment: datetime) -> str:
    # Operational records are timezone-aware UTC; the offset is stored so a read back can never
    # produce a naive timestamp.
    return moment.astimezone(UTC).isoformat()


def _moment(stored: str) -> datetime:
    return datetime.fromisoformat(stored).astimezone(UTC)


class OperationalStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        return self._database_path

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    def save_incident(self, incident: Incident) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO incidents (incident_id, customer_id, created_at, status, outcome, "
                "reason_code, policy_rule, policy_version, transaction_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident.incident_id,
                    incident.customer_id,
                    _stamp(incident.created_at),
                    incident.status.value,
                    incident.outcome.value,
                    incident.reason_code.value,
                    incident.policy_rule.value,
                    incident.policy_version,
                    incident.transaction_id,
                ),
            )

    def finalize_incident(self, incident_id: str, status: WorkflowStatus) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE incidents SET status = ? WHERE incident_id = ?",
                (status.value, incident_id),
            )

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT incident_id, customer_id, created_at, status, outcome, reason_code, "
                "policy_rule, policy_version, transaction_id FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return Incident(
            incident_id=row[0],
            customer_id=row[1],
            created_at=_moment(row[2]),
            status=WorkflowStatus(row[3]),
            outcome=PolicyOutcome(row[4]),
            reason_code=PolicyReasonCode(row[5]),
            policy_rule=PolicyRule(row[6]),
            policy_version=row[7],
            transaction_id=row[8],
        )

    def create_support_case(self, case: SupportCase) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO support_cases (case_id, incident_id, status, recommended_route, "
                    "created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        case.case_id,
                        case.incident_id,
                        case.status.value,
                        case.recommended_route.value,
                        _stamp(case.created_at),
                    ),
                )
        except sqlite3.Error as error:
            raise OperationalStoreError(f"support case {case.case_id} was not written") from error

    def get_support_case(self, case_id: str) -> SupportCase | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT case_id, incident_id, status, recommended_route, created_at "
                    "FROM support_cases WHERE case_id = ?",
                    (case_id,),
                ).fetchone()
        except sqlite3.Error as error:
            raise OperationalStoreError(f"support case {case_id} could not be read back") from error
        if row is None:
            return None
        return SupportCase(
            case_id=row[0],
            incident_id=row[1],
            status=CaseStatus(row[2]),
            recommended_route=SupportRoute(row[3]),
            created_at=_moment(row[4]),
        )

    def record_event(self, event: WorkflowEvent) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO workflow_events (incident_id, occurred_at, event_type, detail) "
                "VALUES (?, ?, ?, ?)",
                (
                    event.incident_id,
                    _stamp(event.occurred_at),
                    event.event_type.value,
                    json.dumps(event.detail, sort_keys=True),
                ),
            )

    def events_for(self, incident_id: str) -> list[WorkflowEvent]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT occurred_at, event_type, detail FROM workflow_events "
                "WHERE incident_id = ? ORDER BY sequence",
                (incident_id,),
            ).fetchall()
        return [
            WorkflowEvent(
                incident_id=incident_id,
                occurred_at=_moment(row[0]),
                event_type=WorkflowEventType(row[1]),
                detail=json.loads(row[2]),
            )
            for row in rows
        ]

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        finally:
            connection.close()

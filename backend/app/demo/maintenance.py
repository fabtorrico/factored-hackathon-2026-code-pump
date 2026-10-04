"""Demo-only maintenance of the local operational state.

A demo is easier to trust when it starts from a known place. This module lets the operator reset
the application-generated operational store — incidents, support cases, workflow events and stored
handoffs — so the agent queue and the resolution flow begin clean.

It touches exactly one file: the SQLite operational database under the configured data root
(`<data_root>/operational/app.db`). It never opens, reads or writes the curated DuckDB database,
the raw organizer sources, or any path outside `<data_root>/operational/`. The reset is explicit:
it only runs when the command is invoked, never on import or on server start.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.workflow.storage import OperationalStore

OPERATIONAL_DIRECTORY = "operational"
OPERATIONAL_FILENAME = "app.db"

# Fixed, code-owned table names. They are only ever interpolated into a count query, never into a
# value, so no caller input reaches SQL.
_OPERATIONAL_TABLES = ("handoffs", "workflow_events", "support_cases", "incidents")


class MaintenanceError(RuntimeError):
    """A demo maintenance action was refused because it was not safe to perform."""


def expected_operational_path(data_root: Path) -> Path:
    """The one operational database path a data root is allowed to have."""

    return Path(data_root) / OPERATIONAL_DIRECTORY / OPERATIONAL_FILENAME


def resolve_operational_path(
    settings: Settings,
    *,
    data_root: Path | None = None,
    database_path: Path | None = None,
) -> Path:
    """Resolve and verify the operational database the reset is allowed to touch.

    The path is always derived from a data root; a caller may pass an explicit `database_path`, but
    it is only accepted when it resolves to that data root's own operational file. This keeps the
    command from ever pointing at `banking.duckdb`, a raw CSV, or any other file.
    """

    root = Path(data_root) if data_root is not None else Path(settings.data_root)
    expected = expected_operational_path(root).resolve()
    if database_path is None:
        return expected

    candidate = Path(database_path).resolve()
    if candidate != expected:
        raise MaintenanceError(
            f"refusing to touch {candidate}: the only operational database is {expected}"
        )
    return candidate


@dataclass(frozen=True, slots=True)
class OperationalStatus:
    """What the operational store currently holds, as plain counts."""

    database_path: Path
    exists: bool
    incidents: int
    support_cases: int
    workflow_events: int
    handoffs: int

    @property
    def total_records(self) -> int:
        return self.incidents + self.support_cases + self.workflow_events + self.handoffs


def _counts(database_path: Path) -> dict[str, int]:
    counts = {name: 0 for name in _OPERATIONAL_TABLES}
    connection = sqlite3.connect(database_path)
    try:
        for name in _OPERATIONAL_TABLES:
            try:
                row = connection.execute(f"SELECT count(*) FROM {name}").fetchone()
            except sqlite3.Error:
                # A store initialized by an older build may lack a table. That is a zero, not a
                # reason to fail the whole status.
                continue
            counts[name] = int(row[0]) if row is not None else 0
    except sqlite3.Error as error:
        raise MaintenanceError(f"the operational database could not be read: {error}") from error
    finally:
        # Windows keeps the file locked until the connection is closed, which would make the reset's
        # own unlink fail. Close before returning anything.
        connection.close()
    return counts


def operational_status(database_path: Path) -> OperationalStatus:
    """Report the operational store's path and record counts without changing anything."""

    path = Path(database_path)
    exists = path.is_file()
    counts = _counts(path) if exists else {name: 0 for name in _OPERATIONAL_TABLES}
    return OperationalStatus(
        database_path=path,
        exists=exists,
        incidents=counts["incidents"],
        support_cases=counts["support_cases"],
        workflow_events=counts["workflow_events"],
        handoffs=counts["handoffs"],
    )


def reset_operational_state(database_path: Path) -> tuple[OperationalStatus, OperationalStatus]:
    """Clear the operational store and recreate its schema, returning before and after counts.

    Deleting the file and re-initializing it guarantees an empty, schema-correct store rather than a
    partial delete. The caller has already verified the path with `resolve_operational_path`.
    """

    path = Path(database_path)
    before = operational_status(path)
    if path.exists():
        try:
            path.unlink()
        except OSError as error:
            raise MaintenanceError(
                "the operational database could not be removed; stop the API server and retry: "
                f"{error}"
            ) from error

    OperationalStore(path).initialize()
    after = operational_status(path)
    return before, after

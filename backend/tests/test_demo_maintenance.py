"""Demo operational-state maintenance.

The safety property under test is scope: the reset may clear the application's own SQLite store and
nothing else. These tests pin that it never touches a neighbouring curated file, that it always
leaves a schema-correct empty store behind, and that a mismatched path is refused.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.demo.__main__ import main
from app.demo.maintenance import (
    MaintenanceError,
    expected_operational_path,
    operational_status,
    reset_operational_state,
    resolve_operational_path,
)
from app.policy import PolicyOutcome, PolicyReasonCode, PolicyRule
from app.workflow.models import (
    CaseStatus,
    Incident,
    SupportCase,
    SupportRoute,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
    new_case_id,
    new_incident_id,
)
from app.workflow.storage import OperationalStore

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def _seed(database_path: Path) -> None:
    store = OperationalStore(database_path)
    store.initialize()
    incident_id = new_incident_id()
    store.save_incident(
        Incident(
            incident_id=incident_id,
            customer_id="CLI-1",
            created_at=NOW,
            status=WorkflowStatus.COMPLETED,
            outcome=PolicyOutcome.ESCALATE,
            reason_code=PolicyReasonCode.PENDING_STATUS,
            policy_rule=PolicyRule.G_PENDING,
            transaction_id="TXN-1",
        )
    )
    store.record_event(
        WorkflowEvent(
            incident_id=incident_id,
            occurred_at=NOW,
            event_type=WorkflowEventType.INCIDENT_CREATED,
        )
    )
    store.create_support_case(
        SupportCase(
            case_id=new_case_id(),
            incident_id=incident_id,
            status=CaseStatus.OPEN,
            recommended_route=SupportRoute.PAYMENTS_OPERATIONS,
            created_at=NOW,
        )
    )


def test_status_of_a_missing_store_is_empty(tmp_path: Path) -> None:
    status = operational_status(expected_operational_path(tmp_path))

    assert status.exists is False
    assert status.total_records == 0


def test_reset_clears_the_store_and_keeps_the_schema(tmp_path: Path) -> None:
    database_path = expected_operational_path(tmp_path)
    _seed(database_path)
    assert operational_status(database_path).total_records > 0

    before, after = reset_operational_state(database_path)

    assert before.incidents == 1
    assert before.support_cases == 1
    assert before.workflow_events == 1
    assert after.total_records == 0
    assert after.exists is True

    # The schema survives, so the API can keep writing without a migrate step.
    store = OperationalStore(database_path)
    store.initialize()
    assert operational_status(database_path).total_records == 0


def test_reset_leaves_a_neighbouring_curated_file_untouched(tmp_path: Path) -> None:
    curated = tmp_path / "processed" / "banking.duckdb"
    curated.parent.mkdir(parents=True)
    curated.write_bytes(b"curated-bytes")
    _seed(expected_operational_path(tmp_path))

    reset_operational_state(expected_operational_path(tmp_path))

    assert curated.read_bytes() == b"curated-bytes"


def test_a_path_outside_the_operational_store_is_refused(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path)
    foreign = tmp_path / "processed" / "banking.duckdb"

    with pytest.raises(MaintenanceError):
        resolve_operational_path(settings, data_root=tmp_path, database_path=foreign)


def test_the_resolved_path_defaults_to_the_operational_file(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path)

    resolved = resolve_operational_path(settings, data_root=tmp_path)

    assert resolved == expected_operational_path(tmp_path).resolve()


def test_cli_status_and_reset_run_against_a_data_root(tmp_path: Path, capsys) -> None:
    _seed(expected_operational_path(tmp_path))

    assert main(["status", "--data-root", str(tmp_path)]) == 0
    assert "operational database" in capsys.readouterr().out

    assert main(["reset", "--data-root", str(tmp_path)]) == 0
    assert operational_status(expected_operational_path(tmp_path)).total_records == 0

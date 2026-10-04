"""Demo operational-state CLI.

    python -m app.demo status [--data-root PATH]
    python -m app.demo reset  [--data-root PATH]

`status` reports what the operational store holds; `reset` clears it and recreates the schema. Both
derive the database path from `--data-root` (defaulting to the configured data root), so neither can
be pointed at the curated DuckDB database or a raw source file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.demo.maintenance import (
    MaintenanceError,
    OperationalStatus,
    expected_operational_path,
    operational_status,
    reset_operational_state,
)


def _build_parser() -> argparse.ArgumentParser:
    default_root = get_settings().data_root
    parser = argparse.ArgumentParser(
        prog="python -m app.demo",
        description="Demo-only maintenance of the local operational store.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("status", "Report the operational store path and record counts."),
        ("reset", "Clear the operational store and recreate its schema."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("--data-root", type=Path, default=default_root)
    return parser


def _print_status(status: OperationalStatus) -> None:
    print(f"operational database: {status.database_path}")
    print(f"  present:         {'yes' if status.exists else 'no'}")
    print(f"  incidents:       {status.incidents}")
    print(f"  support cases:   {status.support_cases}")
    print(f"  workflow events: {status.workflow_events}")
    print(f"  handoffs:        {status.handoffs}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    database_path = expected_operational_path(args.data_root)

    try:
        if args.command == "status":
            _print_status(operational_status(database_path))
            return 0

        before, after = reset_operational_state(database_path)
        print(f"reset operational state: {database_path}")
        print(
            f"  cleared: {before.incidents} incident(s), {before.support_cases} case(s), "
            f"{before.workflow_events} event(s), {before.handoffs} handoff(s)"
        )
        print(
            f"  ready:   {after.incidents} incident(s), {after.support_cases} case(s), "
            f"{after.workflow_events} event(s), {after.handoffs} handoff(s)"
        )
        return 0
    except MaintenanceError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

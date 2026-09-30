import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from app.data.contracts import (
    CONTRACTS,
    CUSTOMERS,
    PRODUCTS,
    TRANSACTIONS,
    ContractViolationError,
    TableContract,
)
from app.data.quality import (
    CheckResult,
    check_customers,
    check_products,
    check_transactions,
    iter_findings,
)

DATABASE_NAME = "banking.duckdb"
REPORT_NAME = "quality_report.json"


@dataclass(frozen=True)
class PipelineResult:
    database_path: Path
    report_path: Path
    report: dict[str, Any]


def _staging_name(contract: TableContract) -> str:
    return f"stg_{contract.key}"


def _stage(con: duckdb.DuckDBPyConnection, contract: TableContract, data_root: Path) -> list[str]:
    source = data_root / contract.source
    staging = _staging_name(contract)
    # all_varchar keeps the raw text so quality checks can tell an unparseable value
    # apart from a genuine NULL, and malformed rows surface as an error.
    try:
        con.execute(
            f"CREATE OR REPLACE TEMP TABLE {staging} AS "
            f"SELECT * FROM read_csv(?, all_varchar=true, header=true)",
            [str(source)],
        )
    except duckdb.Error as exc:
        raise ContractViolationError(
            f"{contract.key}: source unreadable ({contract.source}): {exc}"
        ) from exc
    return [row[0] for row in con.execute(f"DESCRIBE {staging}").fetchall()]


def _validate(contract: TableContract, available: Sequence[str]) -> None:
    missing = contract.missing_columns(frozenset(available))
    if missing:
        raise ContractViolationError(
            f"{contract.key}: required columns missing from {contract.source}: {', '.join(missing)}"
        )


def _curate(con: duckdb.DuckDBPyConnection, contract: TableContract, staging: str) -> list[str]:
    dtype_by_column = {column.name: column.dtype for column in contract.typed_columns}
    # Only the contract's allowlist reaches the curated table; the raw CSV keeps every other
    # column untouched. TRY_CAST retains the row and surfaces the value as NULL; the invalid
    # counts in the quality report make those rows visible instead of dropping them.
    projections = ", ".join(
        f"TRY_CAST({name} AS {dtype_by_column[name]}) AS {name}"
        if name in dtype_by_column
        else name
        for name in contract.curated_columns
    )
    con.execute(f"CREATE OR REPLACE TABLE {contract.table} AS SELECT {projections} FROM {staging}")
    return [row[0] for row in con.execute(f"DESCRIBE {contract.table}").fetchall()]


def _curated_row_count(con: duckdb.DuckDBPyConnection, contract: TableContract) -> int:
    return int(con.execute(f"SELECT count(*) FROM {contract.table}").fetchone()[0])


def _checksum(con: duckdb.DuckDBPyConnection, contract: TableContract) -> str:
    key = contract.primary_key
    digest = con.execute(
        f"SELECT md5(string_agg({key}, ',' ORDER BY {key})) FROM {contract.table}"
    ).fetchone()[0]
    return digest or ""


def _contract_block(
    contract: TableContract, source_columns: Sequence[str], curated_columns: Sequence[str]
) -> dict[str, Any]:
    projected = {column.name for column in contract.typed_columns} & set(curated_columns)
    return {
        "source": contract.source,
        "required_columns": list(contract.required_columns),
        "required_columns_present": True,
        "missing_columns": [],
        "source_column_count": len(source_columns),
        "curated_columns": list(curated_columns),
        "curated_column_count": len(curated_columns),
        "typed_columns_applied": [
            {"name": column.name, "dtype": column.dtype}
            for column in contract.typed_columns
            if column.name in projected
        ],
        "typed_columns_skipped": [
            {"name": column.name, "dtype": column.dtype}
            for column in contract.typed_columns
            if column.name not in projected
        ],
    }


def _run_checks(con: duckdb.DuckDBPyConnection) -> dict[str, CheckResult]:
    return {
        "customers": check_customers(con, _staging_name(CUSTOMERS)),
        "products": check_products(con, _staging_name(PRODUCTS), _staging_name(CUSTOMERS)),
        "transactions": check_transactions(
            con,
            _staging_name(TRANSACTIONS),
            _staging_name(CUSTOMERS),
            _staging_name(PRODUCTS),
            TRANSACTIONS,
        ),
    }


def run_pipeline(data_root: Path) -> PipelineResult:
    processed = data_root / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    database_path = processed / DATABASE_NAME
    report_path = processed / REPORT_NAME

    con = duckdb.connect(str(database_path))
    try:
        columns_by_key: dict[str, list[str]] = {}
        curated_by_key: dict[str, list[str]] = {}
        for contract in CONTRACTS:
            staging = _staging_name(contract)
            source_columns = _stage(con, contract, data_root)
            _validate(contract, source_columns)
            columns_by_key[contract.key] = source_columns
            curated_by_key[contract.key] = _curate(con, contract, staging)

        results = _run_checks(con)
        tables: dict[str, Any] = {}
        for contract in CONTRACTS:
            result = results[contract.key]
            tables[contract.key] = {
                "contract": _contract_block(
                    contract, columns_by_key[contract.key], curated_by_key[contract.key]
                ),
                "source_row_count": result.metrics["row_count"],
                "curated_row_count": _curated_row_count(con, contract),
                "primary_key_checksum": _checksum(con, contract),
                "metrics": {
                    key: value for key, value in result.metrics.items() if key != "row_count"
                },
                "findings": result.findings,
            }

        report = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": "success",
            "duckdb_version": duckdb.__version__,
            "database_path": str(database_path),
            "sources": {contract.key: contract.source for contract in CONTRACTS},
            "tables": tables,
            "finding_count": len(iter_findings(results.values())),
        }
    finally:
        con.close()

    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return PipelineResult(database_path=database_path, report_path=report_path, report=report)

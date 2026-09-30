import csv
from pathlib import Path
from typing import Any

import duckdb
import pytest
from conftest import customer_row, product_row, transaction_row

from app.data.contracts import ContractViolationError
from app.data.pipeline import run_pipeline


def _findings(report: dict[str, Any], table: str) -> dict[str, int]:
    return {item["check"]: item["count"] for item in report["tables"][table]["findings"]}


def _metrics(report: dict[str, Any], table: str) -> dict[str, Any]:
    return report["tables"][table]["metrics"]


def _rewrite_with_columns(path: Path, header: list[str]) -> None:
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    indexes = [rows[0].index(name) for name in header]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows([[row[i] for i in indexes] for row in rows[1:]])


def _transaction_row(database_path: Path, transaction_id: str) -> tuple[Any, ...]:
    con = duckdb.connect(str(database_path), read_only=True)
    try:
        return con.execute(
            "SELECT amount, transaction_date FROM transactions WHERE transaction_id = ?",
            [transaction_id],
        ).fetchone()
    finally:
        con.close()


def test_valid_sources_report_no_findings(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    assert result.report["status"] == "success"
    assert result.report["finding_count"] == 0
    for table in ("customers", "products", "transactions"):
        block = result.report["tables"][table]
        assert block["findings"] == []
        assert block["source_row_count"] == block["curated_row_count"]
        assert block["contract"]["required_columns_present"] is True
        assert block["contract"]["missing_columns"] == []


def test_amount_is_stored_as_decimal(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    con = duckdb.connect(str(result.database_path), read_only=True)
    try:
        declared = con.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'transactions' AND column_name = 'amount'"
        ).fetchone()[0]
        amount = con.execute(
            "SELECT amount FROM transactions WHERE transaction_id = 'TXN-001'"
        ).fetchone()[0]
    finally:
        con.close()

    assert declared == "DECIMAL(18,2)"
    assert float(amount) == 150.00


def test_duplicate_identifiers_are_reported(data_root, valid_rows) -> None:
    rows = {key: list(value) for key, value in valid_rows.items()}
    rows["customers"].append(customer_row())
    rows["products"].append(product_row())
    rows["transactions"].append(
        transaction_row(transaction_date="2026-06-17 10:00:00", amount="10.00", channel="Web")
    )

    report = run_pipeline(data_root(**rows)).report

    assert _metrics(report, "customers")["duplicate_customer_id_values"] == 1
    assert _metrics(report, "customers")["duplicate_customer_id_surplus_rows"] == 1
    assert _findings(report, "customers")["duplicate_customer_id"] == 1
    assert _findings(report, "products")["duplicate_product_id"] == 1
    assert _findings(report, "transactions")["duplicate_transaction_id"] == 1


def test_orphan_foreign_keys_are_reported(data_root, valid_rows) -> None:
    rows = {key: list(value) for key, value in valid_rows.items()}
    rows["products"].append(product_row(product_id="PROD-003", customer_id="CUST-999"))
    rows["transactions"].append(
        transaction_row(
            transaction_id="TXN-002",
            transaction_type="Payment",
            transaction_date="2026-06-17 11:00:00",
            amount="20.00",
            channel="Web",
            product_id="PROD-404",
        )
    )

    report = run_pipeline(data_root(**rows)).report

    assert _metrics(report, "products")["orphan_customer_id"] == 1
    assert _findings(report, "products")["orphan_customer_id"] == 1
    assert _metrics(report, "transactions")["orphan_product_id"] == 1
    assert _findings(report, "transactions")["orphan_product_id"] == 1
    assert _metrics(report, "transactions")["orphan_customer_id"] == 0


def test_product_ownership_mismatch_is_reported(data_root, valid_rows) -> None:
    rows = {key: list(value) for key, value in valid_rows.items()}
    rows["transactions"].append(
        transaction_row(
            transaction_id="TXN-002",
            customer_id="CUST-002",
            transaction_date="2026-06-17 11:00:00",
            amount="20.00",
        )
    )

    report = run_pipeline(data_root(**rows)).report

    assert _metrics(report, "transactions")["ownership_mismatch"] == 1
    assert _findings(report, "transactions")["ownership_mismatch"] == 1


def test_unexpected_categorical_values_are_reported_not_dropped(data_root, valid_rows) -> None:
    rows = {key: list(value) for key, value in valid_rows.items()}
    rows["transactions"].append(
        transaction_row(
            transaction_id="TXN-002",
            transaction_type="Wire",
            transaction_status="Escheated",
            transaction_date="2026-06-17 11:00:00",
            amount="20.00",
            channel="Satellite",
            response_code="99",
        )
    )

    result = run_pipeline(data_root(**rows))
    report = result.report

    assert _findings(report, "transactions")["unexpected_transaction_type"] == 1
    assert _findings(report, "transactions")["unexpected_transaction_status"] == 1
    assert _findings(report, "transactions")["unexpected_channel"] == 1
    assert "Wire" in _metrics(report, "transactions")["transaction_type_distribution"]
    assert "Escheated" in _metrics(report, "transactions")["transaction_status_distribution"]
    assert report["tables"]["transactions"]["curated_row_count"] == 2


def test_unparseable_values_are_counted_and_rows_are_retained(data_root, valid_rows) -> None:
    rows = {key: list(value) for key, value in valid_rows.items()}
    rows["transactions"].append(
        transaction_row(
            transaction_id="TXN-002",
            transaction_type="Payment",
            transaction_date="not-a-date",
            process_date="not-a-date",
            amount="not-a-number",
            amount_usd="not-a-number",
            channel="Web",
        )
    )

    result = run_pipeline(data_root(**rows))
    report = result.report

    assert _findings(report, "transactions")["invalid_amount"] == 1
    assert _findings(report, "transactions")["invalid_transaction_date"] == 1
    assert report["tables"]["transactions"]["curated_row_count"] == 2
    assert _transaction_row(result.database_path, "TXN-002") == (None, None)


def test_source_contract_is_validated_before_projection(data_root, valid_rows) -> None:
    root = data_root(**valid_rows)
    _rewrite_with_columns(root / "raw" / "customers.csv", ["customer_id", "customer_status"])

    with pytest.raises(ContractViolationError, match="detected_accent"):
        run_pipeline(root)


def test_missing_required_column_fails_the_pipeline(data_root, valid_rows) -> None:
    root = data_root(**valid_rows)
    path = root / "sample" / "transactions_20260617.csv"
    with path.open(encoding="utf-8") as handle:
        present = list(csv.reader(handle))[0]
    _rewrite_with_columns(path, [name for name in present if name != "response_code"])

    with pytest.raises(ContractViolationError, match="response_code"):
        run_pipeline(root)


def test_unreadable_source_fails_the_pipeline(data_root, valid_rows) -> None:
    root = data_root(**valid_rows)
    (root / "raw" / "customers.csv").unlink()

    with pytest.raises(ContractViolationError, match="customers"):
        run_pipeline(root)


def test_artifacts_are_written_under_processed(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    assert result.database_path.name == "banking.duckdb"
    assert result.report_path.name == "quality_report.json"
    assert result.database_path.parent == result.report_path.parent
    assert result.database_path.parent.name == "processed"
    assert result.database_path.is_file()
    assert result.report_path.is_file()

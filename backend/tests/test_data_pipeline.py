import duckdb
from conftest import (
    CUSTOMER_DEFAULTS,
    CUSTOMERS_SOURCE_HEADER,
    PRODUCT_DEFAULTS,
    PRODUCTS_SOURCE_HEADER,
    TRANSACTIONS_SOURCE_HEADER,
)

from app.data.contracts import CONTRACTS, CUSTOMERS, PRODUCTS, TRANSACTIONS
from app.data.pipeline import run_pipeline

TABLES = ("customers", "products", "transactions")

PROHIBITED_CUSTOMER_COLUMNS = frozenset(
    {
        "document_number",
        "document_type",
        "first_name",
        "last_name",
        "email",
        "mobile_phone",
        "landline_phone",
        "address",
        "city",
        "state",
        "postal_code",
        "date_of_birth",
        "gender",
        "credit_score",
        "estimated_monthly_income",
        "occupation",
        "marital_status",
        "education_level",
        "registration_date",
        "registration_branch_id",
        "last_updated",
        "accepts_marketing",
    }
)
PROHIBITED_PRODUCT_COLUMNS = frozenset(
    {
        "product_number",
        "credit_limit",
        "interest_rate",
        "opening_date",
        "expiration_date",
        "opening_branch_id",
        "days_past_due",
        "last_transaction_date",
        "last_updated",
    }
)
PROHIBITED_TRANSACTION_COLUMNS = frozenset(
    {
        "latitude",
        "longitude",
        "transaction_category",
        "branch_id",
        "merchant_name",
        "merchant_category",
        "transaction_country",
        "transaction_city",
        "is_fraud",
        "fraud_score",
    }
)
REQUIRED_TRANSACTION_COLUMNS = frozenset(
    {
        "transaction_id",
        "customer_id",
        "product_id",
        "transaction_date",
        "transaction_type",
        "amount",
        "currency",
        "channel",
        "transaction_status",
        "response_code",
    }
)
# Only the transaction record carries the bank's verdict. Nothing on customers or products may be
# read as a decline reason, so a stored balance can never stand in as the cause of a failure.
DECLINE_EVIDENCE_COLUMNS = frozenset({"transaction_status", "response_code"})


def _snapshot(database_path, tables: tuple[str, ...]) -> dict[str, list[tuple]]:
    con = duckdb.connect(str(database_path), read_only=True)
    try:
        return {table: con.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
    finally:
        con.close()


def _curated_columns(database_path, table: str) -> list[str]:
    con = duckdb.connect(str(database_path), read_only=True)
    try:
        return [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
    finally:
        con.close()


def _curated_text(database_path, table: str) -> str:
    return " ".join(
        " ".join("" if value is None else str(value) for value in row)
        for row in _snapshot(database_path, (table,))[table]
    )


def test_pipeline_creates_the_three_curated_tables(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    con = duckdb.connect(str(result.database_path), read_only=True)
    try:
        present = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        columns = {
            table: [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
            for table in ("customers", "products", "transactions")
        }
    finally:
        con.close()

    assert present == {"customers", "products", "transactions"}
    for contract in CONTRACTS:
        assert set(contract.required_columns) <= set(columns[contract.table])


def test_pipeline_is_idempotent(data_root, valid_rows) -> None:
    tables = ("customers", "products", "transactions")

    first = run_pipeline(data_root(**valid_rows))
    first_snapshot = _snapshot(first.database_path, tables)
    first_report = {key: value for key, value in first.report.items() if key != "generated_at"}
    first_report_tables = {
        key: {name: block for name, block in table.items() if name != "primary_key_checksum"}
        for key, table in first_report["tables"].items()
    }

    second = run_pipeline(data_root(**valid_rows))
    second_snapshot = _snapshot(second.database_path, tables)
    second_report = {key: value for key, value in second.report.items() if key != "generated_at"}
    second_report_tables = {
        key: {name: block for name, block in table.items() if name != "primary_key_checksum"}
        for key, table in second_report["tables"].items()
    }

    assert first_snapshot == second_snapshot
    assert first_report_tables == second_report_tables
    assert (
        first.report["tables"]["transactions"]["primary_key_checksum"]
        == second.report["tables"]["transactions"]["primary_key_checksum"]
    )


def test_source_identifiers_are_preserved(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    con = duckdb.connect(str(result.database_path), read_only=True)
    try:
        customers = con.execute("SELECT customer_id FROM customers ORDER BY 1").fetchall()
        products = con.execute("SELECT product_id, customer_id FROM products ORDER BY 1").fetchall()
        transactions = con.execute(
            "SELECT transaction_id, customer_id, product_id, response_code "
            "FROM transactions ORDER BY 1"
        ).fetchall()
    finally:
        con.close()

    assert customers == [("CUST-001",), ("CUST-002",)]
    assert products == [("PROD-001", "CUST-001"), ("PROD-002", "CUST-002")]
    assert transactions == [("TXN-001", "CUST-001", "PROD-001", "00")]


def test_report_records_sources_and_typed_columns(data_root, valid_rows) -> None:
    report = run_pipeline(data_root(**valid_rows)).report

    assert report["sources"] == {
        "customers": "raw/customers.csv",
        "products": "raw/products.csv",
        "transactions": "sample/transactions_20260617.csv",
    }
    assert report["status"] == "success"
    for contract in CONTRACTS:
        block = report["tables"][contract.key]["contract"]
        declared = {column.name for column in contract.typed_columns}
        projected = declared & set(contract.curated_columns)
        assert {item["name"] for item in block["typed_columns_applied"]} == projected
        assert {item["name"] for item in block["typed_columns_skipped"]} == declared - projected
        assert set(block["curated_columns"]) == set(contract.curated_columns)
        assert block["curated_column_count"] == len(contract.curated_columns)
    for key in TABLES:
        assert (
            report["tables"][key]["contract"]["curated_column_count"]
            < report["tables"][key]["contract"]["source_column_count"]
        )


def test_report_contains_no_customer_level_columns(data_root, valid_rows) -> None:
    report = run_pipeline(data_root(**valid_rows)).report
    serialised = str(report)

    excluded = (
        PROHIBITED_CUSTOMER_COLUMNS
        | PROHIBITED_PRODUCT_COLUMNS
        | frozenset({"document_number", "first_name", "last_name", "email", "product_number"})
    )
    assert not [name for name in excluded if name in serialised]


def test_fixtures_carry_pii_so_the_projection_is_exercised() -> None:
    assert set(CUSTOMERS_SOURCE_HEADER) >= PROHIBITED_CUSTOMER_COLUMNS
    assert set(PRODUCTS_SOURCE_HEADER) >= PROHIBITED_PRODUCT_COLUMNS
    assert set(TRANSACTIONS_SOURCE_HEADER) >= PROHIBITED_TRANSACTION_COLUMNS
    for contract in CONTRACTS:
        source_header = {
            "customers": CUSTOMERS_SOURCE_HEADER,
            "products": PRODUCTS_SOURCE_HEADER,
            "transactions": TRANSACTIONS_SOURCE_HEADER,
        }[contract.key]
        assert len(source_header) > len(contract.curated_columns)


def test_curated_customers_table_excludes_pii_columns(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    columns = _curated_columns(result.database_path, "customers")

    assert columns == list(CUSTOMERS.curated_columns)
    assert {"customer_id", "country", "detected_accent", "segment", "customer_status"} <= set(
        columns
    )
    assert not PROHIBITED_CUSTOMER_COLUMNS & set(columns)


def test_curated_products_table_excludes_account_identifiers_and_limits(
    data_root, valid_rows
) -> None:
    result = run_pipeline(data_root(**valid_rows))

    columns = _curated_columns(result.database_path, "products")

    assert columns == list(PRODUCTS.curated_columns)
    assert "product_number" not in columns
    assert "credit_limit" not in columns
    assert not PROHIBITED_PRODUCT_COLUMNS & set(columns)


def test_curated_transactions_table_holds_only_approved_columns(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    columns = _curated_columns(result.database_path, "transactions")

    assert columns == list(TRANSACTIONS.curated_columns)
    assert set(columns) >= REQUIRED_TRANSACTION_COLUMNS
    assert "latitude" not in columns
    assert "longitude" not in columns
    assert not PROHIBITED_TRANSACTION_COLUMNS & set(columns)
    assert set(columns) < set(TRANSACTIONS_SOURCE_HEADER)


def test_decline_cause_comes_only_from_the_transaction_record(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    columns = {table: set(_curated_columns(result.database_path, table)) for table in TABLES}

    assert "current_balance" in columns["products"]
    assert columns["transactions"] >= DECLINE_EVIDENCE_COLUMNS
    for table in ("customers", "products"):
        assert not DECLINE_EVIDENCE_COLUMNS & columns[table]


def test_pii_values_never_reach_the_curated_tables(data_root, valid_rows) -> None:
    result = run_pipeline(data_root(**valid_rows))

    customers_text = _curated_text(result.database_path, "customers")
    products_text = _curated_text(result.database_path, "products")
    leaked = [
        column
        for column, value in {**CUSTOMER_DEFAULTS, **PRODUCT_DEFAULTS}.items()
        if column not in CUSTOMERS.curated_columns
        and column not in PRODUCTS.curated_columns
        and len(value) >= 5
        and (value in customers_text or value in products_text)
    ]

    assert leaked == []

import csv
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

# The organizers ship every one of these columns. The fixtures reproduce the full source
# headers - PII included - so the curated DuckDB tables are proven to drop them.
CUSTOMERS_SOURCE_HEADER = [
    "customer_id",
    "document_number",
    "document_type",
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "email",
    "mobile_phone",
    "landline_phone",
    "address",
    "city",
    "state",
    "country",
    "postal_code",
    "detected_accent",
    "segment",
    "credit_score",
    "estimated_monthly_income",
    "occupation",
    "marital_status",
    "education_level",
    "registration_date",
    "registration_branch_id",
    "customer_status",
    "last_updated",
    "accepts_marketing",
]

PRODUCTS_SOURCE_HEADER = [
    "product_id",
    "customer_id",
    "product_type",
    "product_number",
    "currency",
    "current_balance",
    "credit_limit",
    "interest_rate",
    "opening_date",
    "expiration_date",
    "opening_branch_id",
    "product_status",
    "opening_channel",
    "has_linked_app",
    "days_past_due",
    "last_transaction_date",
    "last_updated",
]

TRANSACTIONS_SOURCE_HEADER = [
    "transaction_id",
    "transaction_date",
    "process_date",
    "product_id",
    "customer_id",
    "transaction_type",
    "transaction_category",
    "amount",
    "currency",
    "amount_usd",
    "channel",
    "branch_id",
    "merchant_name",
    "merchant_category",
    "transaction_country",
    "transaction_city",
    "transaction_status",
    "response_code",
    "is_fraud",
    "fraud_score",
    "latitude",
    "longitude",
]

CUSTOMER_DEFAULTS: dict[str, str] = {
    "customer_id": "CUST-001",
    "document_number": "G8637940",
    "document_type": "Pasaporte",
    "first_name": "Samuel",
    "last_name": "Diaz Perez",
    "date_of_birth": "1967-06-18",
    "gender": "M",
    "email": "samuel.diaz@example.com",
    "mobile_phone": "+57 315 564 6977",
    "landline_phone": "+57 4 314 5374",
    "address": "Calle 433 #4-21, Barrio Bocagrande",
    "city": "Cartagena",
    "state": "Bolivar",
    "country": "CO",
    "postal_code": "130010",
    "detected_accent": "colombian",
    "segment": "Retail",
    "credit_score": "701",
    "estimated_monthly_income": "24678431.94",
    "occupation": "Administrative",
    "marital_status": "Married",
    "education_level": "University",
    "registration_date": "2021-07-30 05:39:39",
    "registration_branch_id": "SUC-7R3DCC91",
    "customer_status": "Active",
    "last_updated": "2021-08-15 05:39:39",
    "accepts_marketing": "False",
}

PRODUCT_DEFAULTS: dict[str, str] = {
    "product_id": "PROD-001",
    "customer_id": "CUST-001",
    "product_type": "Checking",
    "product_number": "4332181960",
    "currency": "USD",
    "current_balance": "1250.75",
    "credit_limit": "",
    "interest_rate": "0.0",
    "opening_date": "2020-03-18",
    "expiration_date": "",
    "opening_branch_id": "SUC-E1VTXGEU",
    "product_status": "Active",
    "opening_channel": "Web",
    "has_linked_app": "True",
    "days_past_due": "",
    "last_transaction_date": "2025-07-08 17:19:16",
    "last_updated": "2025-12-25 00:57:58",
}

TRANSACTION_DEFAULTS: dict[str, str] = {
    "transaction_id": "TXN-001",
    "transaction_date": "2026-06-17 09:15:00",
    "process_date": "2026-06-17",
    "product_id": "PROD-001",
    "customer_id": "CUST-001",
    "transaction_type": "Transfer",
    "transaction_category": "Wages",
    "amount": "150.00",
    "currency": "USD",
    "amount_usd": "150.00",
    "channel": "App",
    "branch_id": "",
    "merchant_name": "",
    "merchant_category": "",
    "transaction_country": "United States",
    "transaction_city": "Miami",
    "transaction_status": "Approved",
    "response_code": "00",
    "is_fraud": "False",
    "fraud_score": "",
    "latitude": "",
    "longitude": "",
}

Row = Sequence[str | None]


def _build_row(
    header: Sequence[str], defaults: dict[str, str], overrides: dict[str, Any]
) -> list[str]:
    return [str(overrides.get(name, defaults.get(name, ""))) for name in header]


def customer_row(**overrides: Any) -> list[str]:
    return _build_row(CUSTOMERS_SOURCE_HEADER, CUSTOMER_DEFAULTS, overrides)


def product_row(**overrides: Any) -> list[str]:
    return _build_row(PRODUCTS_SOURCE_HEADER, PRODUCT_DEFAULTS, overrides)


def transaction_row(**overrides: Any) -> list[str]:
    return _build_row(TRANSACTIONS_SOURCE_HEADER, TRANSACTION_DEFAULTS, overrides)


def _write_csv(path: Path, header: list[str], rows: Sequence[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


DataRootFactory = Callable[..., Path]


@pytest.fixture
def data_root(tmp_path: Path) -> DataRootFactory:
    def build(
        customers: Sequence[Row] = (),
        products: Sequence[Row] = (),
        transactions: Sequence[Row] = (),
    ) -> Path:
        root = tmp_path / "data"
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "sample").mkdir(parents=True, exist_ok=True)
        _write_csv(root / "raw" / "customers.csv", CUSTOMERS_SOURCE_HEADER, customers)
        _write_csv(root / "raw" / "products.csv", PRODUCTS_SOURCE_HEADER, products)
        _write_csv(
            root / "sample" / "transactions_20260617.csv", TRANSACTIONS_SOURCE_HEADER, transactions
        )
        return root

    return build


@pytest.fixture
def valid_rows() -> dict[str, list[str]]:
    return {
        "customers": [
            customer_row(),
            customer_row(customer_id="CUST-002", segment="Premium", detected_accent="argentine"),
        ],
        "products": [
            product_row(),
            product_row(product_id="PROD-002", customer_id="CUST-002", product_type="CreditCard"),
        ],
        "transactions": [transaction_row()],
    }

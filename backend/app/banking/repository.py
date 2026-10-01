from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from app.banking.errors import DataUnavailableError
from app.banking.models import (
    CandidateFilters,
    CustomerRecord,
    ProductRecord,
    TransactionFilters,
    TransactionRecord,
)

# Column lists are literals, never caller input: filters bind values as query parameters and
# cannot reach the SQL text.
CUSTOMER_COLUMNS = "customer_id, customer_status, segment, country, detected_accent"
PRODUCT_COLUMNS = (
    "product_id, customer_id, product_type, product_status, currency, current_balance, "
    "opening_channel, has_linked_app"
)
TRANSACTION_COLUMNS = (
    "transaction_id, customer_id, product_id, transaction_date, process_date, transaction_type, "
    "amount, currency, amount_usd, channel, transaction_status, response_code"
)
TRANSACTION_ORDER = "ORDER BY transaction_date DESC NULLS LAST, transaction_id ASC"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return None


class CuratedBankingRepository:
    """Read-only access to the curated DuckDB tables produced by `python -m app.data`.

    Only curated columns are selectable, and every read is scoped to an explicit customer_id, so
    the curated layer stays the single place where data minimization is decided.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def _connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        if not self._database_path.is_file():
            raise DataUnavailableError(f"curated database missing: {self._database_path}")
        try:
            connection = duckdb.connect(str(self._database_path), read_only=True)
        except duckdb.Error as exc:
            raise DataUnavailableError(f"curated database cannot be opened: {exc}") from exc
        try:
            yield connection
        except duckdb.Error as exc:
            raise DataUnavailableError(f"curated query failed: {exc}") from exc
        finally:
            connection.close()

    def find_customer(self, customer_id: str) -> CustomerRecord | None:
        sql = f"SELECT {CUSTOMER_COLUMNS} FROM customers WHERE customer_id = ?"
        with self._connection() as connection:
            row = connection.execute(sql, [customer_id]).fetchone()
        if row is None:
            return None
        return CustomerRecord(
            customer_id=_text(row[0]) or "",
            customer_status=_text(row[1]),
            segment=_text(row[2]),
            country=_text(row[3]),
            detected_accent=_text(row[4]),
        )

    def list_products(self, customer_id: str) -> list[ProductRecord]:
        sql = (
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE customer_id = ? ORDER BY product_id ASC"
        )
        with self._connection() as connection:
            rows = connection.execute(sql, [customer_id]).fetchall()
        return [
            ProductRecord(
                product_id=_text(row[0]) or "",
                customer_id=_text(row[1]) or "",
                product_type=_text(row[2]),
                product_status=_text(row[3]),
                currency=_text(row[4]),
                current_balance=_number(row[5]),
                opening_channel=_text(row[6]),
                has_linked_app=None if row[7] is None else bool(row[7]),
            )
            for row in rows
        ]

    def find_transaction(self, transaction_id: str) -> TransactionRecord | None:
        sql = f"SELECT {TRANSACTION_COLUMNS} FROM transactions WHERE transaction_id = ?"
        with self._connection() as connection:
            row = connection.execute(sql, [transaction_id]).fetchone()
        return None if row is None else _transaction(row)

    def list_transactions(
        self, customer_id: str, filters: TransactionFilters | CandidateFilters
    ) -> list[TransactionRecord]:
        clauses = ["customer_id = ?"]
        parameters: list[Any] = [customer_id]
        for column, value in (
            ("transaction_type", filters.transaction_type),
            ("transaction_status", filters.transaction_status),
            ("channel", filters.channel),
            ("currency", filters.currency),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        if filters.date_from is not None:
            clauses.append("transaction_date >= ?")
            parameters.append(datetime.combine(filters.date_from, time.min))
        if filters.date_to is not None:
            # date_to is inclusive, so the upper bound is the start of the next day.
            clauses.append("transaction_date < ?")
            parameters.append(datetime.combine(filters.date_to + timedelta(days=1), time.min))
        if isinstance(filters, CandidateFilters):
            # A NULL amount never satisfies a range clause; such rows are simply not candidates.
            if filters.amount_min is not None:
                clauses.append("amount >= ?")
                parameters.append(filters.amount_min)
            if filters.amount_max is not None:
                clauses.append("amount <= ?")
                parameters.append(filters.amount_max)
        sql = (
            f"SELECT {TRANSACTION_COLUMNS} FROM transactions "
            f"WHERE {' AND '.join(clauses)} {TRANSACTION_ORDER} LIMIT ?"
        )
        parameters.append(filters.limit)
        with self._connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_transaction(row) for row in rows]


def _transaction(row: tuple[Any, ...]) -> TransactionRecord:
    return TransactionRecord(
        transaction_id=_text(row[0]) or "",
        customer_id=_text(row[1]) or "",
        product_id=_text(row[2]),
        transaction_date=row[3],
        process_date=row[4],
        transaction_type=_text(row[5]),
        amount=_number(row[6]),
        currency=_text(row[7]),
        amount_usd=_number(row[8]),
        channel=_text(row[9]),
        transaction_status=_text(row[10]),
        response_code=_text(row[11]),
    )

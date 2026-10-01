import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.banking.errors import InvalidRequestError

CURRENCY_PATTERN = re.compile(r"[A-Z]{3}")
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class CustomerRecord(BaseModel):
    """The only customer attributes a tool may expose. Curated table, no PII columns."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    customer_status: str | None = None
    segment: str | None = None
    country: str | None = None
    detected_accent: str | None = None


class ProductRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    customer_id: str
    product_type: str | None = None
    product_status: str | None = None
    currency: str | None = None
    # Context only. current_balance is never evidence for why a transaction failed.
    current_balance: float | None = None
    opening_channel: str | None = None
    has_linked_app: bool | None = None


class TransactionRecord(BaseModel):
    """A curated transaction as the bank recorded it.

    transaction_status is the verified verdict and response_code is reported verbatim because
    its semantics are undocumented. Neither this model nor any banking tool derives a cause for a
    failure: "Declined" is a fact, "declined for lack of funds" is not.
    """

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    customer_id: str
    product_id: str | None = None
    transaction_date: datetime | None = None
    process_date: datetime | None = None
    transaction_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    amount_usd: float | None = None
    channel: str | None = None
    transaction_status: str | None = None
    response_code: str | None = None


class CustomerContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    customer: CustomerRecord
    products: list[ProductRecord]


class OwnershipVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    transaction_id: str
    customer_id: str
    owned: bool
    # Ownership is proven by the transaction's customer_id matching the session customer. An
    # absent transaction and one owned by somebody else both return owned=False.
    verified_by: Literal["transaction_customer_id"] = "transaction_customer_id"


def _optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _optional_date(raw: Any, field: str) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    value = _optional_text(raw)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRequestError(f"{field} is not an ISO date: {value!r}") from exc


def _optional_float(raw: Any, field: str) -> float | None:
    value = _optional_text(raw)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise InvalidRequestError(f"{field} is not a number: {value!r}") from exc


def _limit(raw: Any) -> int:
    value = _optional_text(raw)
    if value is None:
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except ValueError as exc:
        raise InvalidRequestError(f"limit is not an integer: {value!r}") from exc
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidRequestError(f"limit must be between 1 and {MAX_LIMIT}: {limit}")
    return limit


class TransactionFilters(BaseModel):
    """The complete, closed set of filters a transaction read accepts.

    There is no query language: each field maps to one equality or range clause in the
    repository, so a caller cannot widen a read beyond the authenticated customer's rows.
    """

    model_config = ConfigDict(frozen=True)

    transaction_type: str | None = None
    transaction_status: str | None = None
    channel: str | None = None
    currency: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = DEFAULT_LIMIT

    # Validation runs on construction, not only through parse(), so a malformed filter raises the
    # domain error the API layer knows how to report instead of a framework validation error.
    @field_validator("transaction_type", "transaction_status", "channel", mode="before")
    @classmethod
    def _text(cls, raw: Any) -> str | None:
        return _optional_text(raw)

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, raw: Any) -> str | None:
        value = _optional_text(raw)
        if value is not None and not CURRENCY_PATTERN.fullmatch(value):
            raise InvalidRequestError(f"currency is not an ISO code: {value!r}")
        return value

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _day(cls, raw: Any, info: ValidationInfo) -> date | None:
        return _optional_date(raw, info.field_name)

    @field_validator("limit", mode="before")
    @classmethod
    def _bounded_limit(cls, raw: Any) -> int:
        return _limit(raw)


class CandidateFilters(TransactionFilters):
    """Deterministic narrowing for ambiguous customer references. Not semantic search."""

    amount_min: float | None = None
    amount_max: float | None = None

    @field_validator("amount_min", "amount_max", mode="before")
    @classmethod
    def _amount(cls, raw: Any, info: ValidationInfo) -> float | None:
        return _optional_float(raw, info.field_name)


class CustomerTransactions(BaseModel):
    model_config = ConfigDict(frozen=True)

    customer_id: str
    filters: TransactionFilters
    transactions: list[TransactionRecord]


class CandidateSearch(BaseModel):
    model_config = ConfigDict(frozen=True)

    customer_id: str
    filters: CandidateFilters
    candidates: list[TransactionRecord]

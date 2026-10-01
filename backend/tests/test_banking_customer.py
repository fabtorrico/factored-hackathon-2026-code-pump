import pytest
from conftest import ABSENT_CUSTOMER, CUSTOMER_DEFAULTS, OTHER, OWNER
from pydantic import BaseModel

from app.banking.errors import (
    CustomerNotFoundError,
    InvalidRequestError,
    Reason,
    UnauthorizedResourceError,
)
from app.banking.service import BankingService
from app.data.contracts import CUSTOMERS, PRODUCTS

CURATED_CUSTOMER_FIELDS = {
    "customer_id",
    "customer_status",
    "segment",
    "country",
    "detected_accent",
}
CURATED_PRODUCT_FIELDS = {
    "product_id",
    "customer_id",
    "product_type",
    "product_status",
    "currency",
    "current_balance",
    "opening_channel",
    "has_linked_app",
}


def _fields(model: BaseModel) -> set[str]:
    return set(type(model).model_fields)


def test_customer_reads_own_context(service: BankingService, customer_session: str) -> None:
    context = service.get_customer_context(customer_session, OWNER)

    assert context.customer.customer_id == OWNER
    assert context.customer.segment == "Retail"
    assert context.customer.detected_accent == "colombian"
    assert [product.product_id for product in context.products] == ["PROD-001", "PROD-002"]


def test_context_exposes_only_curated_columns(
    service: BankingService, customer_session: str
) -> None:
    context = service.get_customer_context(customer_session)

    assert _fields(context.customer) == CURATED_CUSTOMER_FIELDS
    assert _fields(context.products[0]) == CURATED_PRODUCT_FIELDS


def test_context_never_carries_raw_pii_values(
    service: BankingService, customer_session: str
) -> None:
    context = service.get_customer_context(customer_session)

    curated = set(CUSTOMERS.curated_columns) | set(PRODUCTS.curated_columns)
    serialised = context.model_dump_json()
    excluded = [
        value
        for column, value in CUSTOMER_DEFAULTS.items()
        if column not in curated and len(value) >= 5
    ]

    assert [value for value in excluded if value in serialised] == []


def test_customer_cannot_read_another_customers_context(
    service: BankingService, customer_session: str
) -> None:
    with pytest.raises(UnauthorizedResourceError) as denied:
        service.get_customer_context(customer_session, OTHER)

    assert denied.value.reason is Reason.UNAUTHORIZED_RESOURCE
    assert denied.value.customer_id == OWNER
    assert "Premium" not in denied.value.message


def test_omitting_the_customer_id_resolves_to_the_session_customer(
    service: BankingService, customer_session: str
) -> None:
    assert service.get_customer_context(customer_session).customer.customer_id == OWNER


def test_blank_customer_id_is_rejected_as_input(
    service: BankingService, customer_session: str
) -> None:
    with pytest.raises(InvalidRequestError) as invalid:
        service.get_customer_context(customer_session, "   ")

    assert invalid.value.reason is Reason.INVALID_REQUEST


def test_surrounding_whitespace_does_not_break_identity_matching(
    service: BankingService, customer_session: str
) -> None:
    assert service.get_customer_context(customer_session, f" {OWNER} ").customer.customer_id == (
        OWNER
    )


def test_session_without_a_curated_record_is_a_not_found(
    service: BankingService,
) -> None:
    session = service.create_session(ABSENT_CUSTOMER)

    with pytest.raises(CustomerNotFoundError) as missing:
        service.get_customer_context(session.session_id)

    assert missing.value.reason is Reason.CUSTOMER_NOT_FOUND
    assert missing.value.customer_id == ABSENT_CUSTOMER


def test_other_customer_reads_only_their_own_context(
    service: BankingService, other_session: str
) -> None:
    context = service.get_customer_context(other_session, OTHER)

    assert context.customer.customer_id == OTHER
    assert [product.product_id for product in context.products] == ["PROD-003"]
    assert [product.customer_id for product in context.products] == [OTHER]

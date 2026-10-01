import pytest
from conftest import ABSENT_CUSTOMER, OTHER, OWNER

from app.banking.errors import Reason, TransactionNotFoundError, UnauthorizedResourceError
from app.banking.models import CandidateFilters, TransactionFilters
from app.banking.service import BankingService
from app.data.contracts import TRANSACTIONS


def test_customer_reads_own_transaction(service: BankingService, customer_session: str) -> None:
    record = service.get_transaction(customer_session, "TXN-002")

    assert record.transaction_id == "TXN-002"
    assert record.customer_id == OWNER
    assert record.transaction_status == "Declined"
    assert record.response_code == "51"
    assert record.amount == 40.0


def test_transaction_record_exposes_only_curated_columns(
    service: BankingService, customer_session: str
) -> None:
    record = service.get_transaction(customer_session, "TXN-002")

    assert set(record.model_dump(exclude_none=True)) == set(TRANSACTIONS.curated_columns)


def test_missing_optional_columns_read_back_as_absent(
    service: BankingService, customer_session: str
) -> None:
    record = service.get_transaction(customer_session, "TXN-003")

    assert record.response_code is None
    assert record.amount_usd is None
    assert record.transaction_status == "Pending"


def test_customer_cannot_read_another_customers_transaction(
    service: BankingService, customer_session: str
) -> None:
    with pytest.raises(TransactionNotFoundError) as denied:
        service.get_transaction(customer_session, "TXN-004")

    assert denied.value.reason is Reason.TRANSACTION_NOT_FOUND
    assert "TXN-004" not in denied.value.message


def test_absent_and_foreign_transactions_are_indistinguishable(
    service: BankingService, customer_session: str
) -> None:
    absent = pytest.raises(
        TransactionNotFoundError, service.get_transaction, customer_session, "TXN-999"
    )
    foreign = pytest.raises(
        TransactionNotFoundError, service.get_transaction, customer_session, "TXN-004"
    )

    assert absent.value.message == foreign.value.message
    assert absent.value.reason is foreign.value.reason


def test_customer_cannot_bypass_authorization_with_another_customer_id(
    service: BankingService, customer_session: str
) -> None:
    with pytest.raises(UnauthorizedResourceError) as denied:
        service.get_customer_transactions(customer_session, None, OTHER)

    assert denied.value.reason is Reason.UNAUTHORIZED_RESOURCE

    with pytest.raises(UnauthorizedResourceError):
        service.find_candidate_transactions(customer_session, None, OTHER)


def test_transaction_list_returns_only_owned_transactions(
    service: BankingService, customer_session: str
) -> None:
    result = service.get_customer_transactions(customer_session)

    assert result.customer_id == OWNER
    assert [record.transaction_id for record in result.transactions] == [
        "TXN-003",
        "TXN-002",
        "TXN-001",
    ]
    assert {record.customer_id for record in result.transactions} == {OWNER}


def test_transaction_list_is_deterministic(service: BankingService, customer_session: str) -> None:
    first = service.get_customer_transactions(customer_session)
    second = service.get_customer_transactions(customer_session)

    assert [record.model_dump() for record in first.transactions] == [
        record.model_dump() for record in second.transactions
    ]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (TransactionFilters(transaction_type="Transfer"), ["TXN-003", "TXN-001"]),
        (TransactionFilters(transaction_status="Declined"), ["TXN-002"]),
        (TransactionFilters(channel="Web"), ["TXN-003"]),
        (TransactionFilters(currency="USD"), ["TXN-003", "TXN-002", "TXN-001"]),
        (TransactionFilters(date_from="2026-06-16", date_to="2026-06-16"), ["TXN-002"]),
        (TransactionFilters(date_from="2026-06-17"), ["TXN-003"]),
        (TransactionFilters(limit=2), ["TXN-003", "TXN-002"]),
        (
            TransactionFilters(transaction_type="Transfer", transaction_status="Approved"),
            ["TXN-001"],
        ),
    ],
)
def test_filters_narrow_deterministically(
    service: BankingService, customer_session: str, filters, expected: list[str]
) -> None:
    result = service.get_customer_transactions(customer_session, filters)

    assert [record.transaction_id for record in result.transactions] == expected
    assert result.filters == filters


def test_filters_never_reach_another_customers_rows(
    service: BankingService, other_session: str
) -> None:
    result = service.get_customer_transactions(
        other_session, TransactionFilters(date_from="2026-06-16")
    )

    assert [record.transaction_id for record in result.transactions] == ["TXN-005", "TXN-004"]
    assert {record.customer_id for record in result.transactions} == {OTHER}


def test_candidate_search_returns_every_owned_match(
    service: BankingService, customer_session: str
) -> None:
    result = service.find_candidate_transactions(
        customer_session, CandidateFilters(transaction_type="Transfer")
    )

    assert [record.transaction_id for record in result.candidates] == ["TXN-003", "TXN-001"]
    assert result.customer_id == OWNER


def test_candidate_search_supports_amount_ranges(
    service: BankingService, customer_session: str
) -> None:
    result = service.find_candidate_transactions(
        customer_session, CandidateFilters(amount_min="100", amount_max="500")
    )

    assert [record.transaction_id for record in result.candidates] == ["TXN-001"]


def test_candidate_search_never_returns_another_customers_candidates(
    service: BankingService, other_session: str
) -> None:
    result = service.find_candidate_transactions(
        other_session, CandidateFilters(transaction_type="Transfer")
    )

    assert [record.transaction_id for record in result.candidates] == ["TXN-005", "TXN-006"]


def test_candidate_search_without_matches_is_a_verified_empty_result(
    service: BankingService, customer_session: str
) -> None:
    result = service.find_candidate_transactions(
        customer_session, CandidateFilters(transaction_status="Reversed")
    )

    assert result.candidates == []
    assert result.customer_id == OWNER


def test_correct_ownership_is_verified(service: BankingService, customer_session: str) -> None:
    verification = service.verify_transaction_ownership(customer_session, "TXN-001")

    assert verification.owned is True
    assert verification.customer_id == OWNER
    assert verification.transaction_id == "TXN-001"
    assert verification.verified_by == "transaction_customer_id"


@pytest.mark.parametrize("transaction_id", ["TXN-004", "TXN-999"])
def test_incorrect_ownership_fails_safely(
    service: BankingService, customer_session: str, transaction_id: str
) -> None:
    verification = service.verify_transaction_ownership(customer_session, transaction_id)

    assert verification.owned is False
    assert verification.customer_id == OWNER


def test_ownership_check_for_a_session_without_records_is_denied(
    service: BankingService,
) -> None:
    session = service.create_session(ABSENT_CUSTOMER)

    verification = service.verify_transaction_ownership(session.session_id, "TXN-001")

    assert verification.owned is False

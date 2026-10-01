import os

import pytest
from conftest import OWNER

from app.banking.errors import DataUnavailableError, InvalidRequestError, Reason
from app.banking.models import CandidateFilters, TransactionFilters
from app.banking.repository import CuratedBankingRepository
from app.banking.service import BankingService


def test_missing_database_fails_before_any_read(
    service_without_data: BankingService,
) -> None:
    session = service_without_data.create_session(OWNER)

    with pytest.raises(DataUnavailableError) as unavailable:
        service_without_data.get_customer_context(session.session_id)

    assert unavailable.value.reason is Reason.DATA_UNAVAILABLE


def test_missing_file_is_reported_as_unavailable(tmp_path) -> None:
    repository = CuratedBankingRepository(tmp_path / "nothing" / "banking.duckdb")

    with pytest.raises(DataUnavailableError):
        repository.find_customer(OWNER)


def test_unreadable_database_fails_safely(tmp_path) -> None:
    corrupt = tmp_path / "banking.duckdb"
    corrupt.write_bytes(b"this is not a duckdb database")

    repository = CuratedBankingRepository(corrupt)

    with pytest.raises(DataUnavailableError):
        repository.find_customer(OWNER)


@pytest.mark.parametrize(
    ("raw", "offending_field"),
    [
        ({"currency": "dollars"}, "currency"),
        ({"date_from": "not-a-date"}, "date_from"),
        ({"date_to": "17-06-2026"}, "date_to"),
        ({"limit": 0}, "limit"),
        ({"limit": 1000}, "limit"),
    ],
)
def test_unparsable_filters_are_rejected_at_construction(
    raw: dict[str, object], offending_field: str
) -> None:
    with pytest.raises(InvalidRequestError) as invalid:
        TransactionFilters(**raw)

    assert invalid.value.reason is Reason.INVALID_REQUEST
    assert offending_field in invalid.value.detail


@pytest.mark.parametrize(
    ("raw", "offending_field"),
    [
        ({"transaction_type": "Wire"}, "transaction_type"),
        ({"transaction_status": "Escheated"}, "transaction_status"),
        ({"channel": "Satellite"}, "channel"),
        ({"date_from": "2026-06-17", "date_to": "2026-06-16"}, "date_from"),
    ],
)
def test_out_of_domain_filters_are_rejected_by_the_service(
    service: BankingService, customer_session: str, raw: dict[str, object], offending_field: str
) -> None:
    with pytest.raises(InvalidRequestError) as invalid:
        service.get_customer_transactions(customer_session, TransactionFilters(**raw))

    assert invalid.value.reason is Reason.INVALID_REQUEST
    assert offending_field in invalid.value.detail


def test_default_filter_is_applied_when_none_is_given(
    service: BankingService, customer_session: str
) -> None:
    result = service.get_customer_transactions(customer_session, None)

    assert result.filters.limit == 20


def test_reversed_candidate_amount_range_is_rejected(
    service: BankingService, customer_session: str
) -> None:
    with pytest.raises(InvalidRequestError) as invalid:
        service.find_candidate_transactions(
            customer_session, CandidateFilters(amount_min="900.00", amount_max="10.00")
        )

    assert "amount_min" in invalid.value.detail


def test_unparsable_candidate_amount_is_rejected() -> None:
    with pytest.raises(InvalidRequestError):
        CandidateFilters(amount_min="a lot")


@pytest.mark.parametrize("identifier", ["", "   "])
def test_blank_transaction_identifier_is_rejected(
    service: BankingService, customer_session: str, identifier: str
) -> None:
    with pytest.raises(InvalidRequestError):
        service.get_transaction(customer_session, identifier)


def test_unexpected_tool_failure_is_audited_as_tool_failure(
    service: BankingService, customer_session: str, audit_sink, monkeypatch
) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(service._repository, "find_customer", explode)

    with pytest.raises(RuntimeError):
        service.get_customer_context(customer_session)

    event = audit_sink.recent(limit=1)[0]
    assert event.outcome == "failed"
    assert event.reason is Reason.TOOL_FAILURE


def test_data_failure_message_exposes_no_internals(
    service_without_data: BankingService,
) -> None:
    session = service_without_data.create_session(OWNER)

    with pytest.raises(DataUnavailableError) as unavailable:
        service_without_data.get_transaction(session.session_id, "TXN-001")

    message = unavailable.value.message
    assert "banking.duckdb" not in message
    assert "SELECT" not in message
    assert os.sep not in message

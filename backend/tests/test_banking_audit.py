import pytest
from conftest import CUSTOMER_DEFAULTS, OTHER, OWNER, SESSION_TTL

from app.banking.audit import InMemoryAuditSink, fingerprint
from app.banking.errors import (
    DataUnavailableError,
    ExpiredSessionError,
    InvalidSessionError,
    Reason,
    TransactionNotFoundError,
    UnauthorizedResourceError,
)
from app.banking.models import CandidateFilters, TransactionFilters
from app.banking.service import BankingService
from app.data.contracts import CUSTOMERS, PRODUCTS


def _only(sink: InMemoryAuditSink):
    return sink.recent(limit=1)[0]


def test_successful_call_is_audited(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink, clock
) -> None:
    service.get_customer_context(customer_session)

    event = _only(audit_sink)
    assert event.tool == "get_customer_context"
    assert event.outcome == "success"
    assert event.reason is None
    assert event.customer_id == OWNER
    assert event.resource_type == "customer"
    assert event.occurred_at == clock()
    assert event.latency_ms >= 0


def test_read_is_audited_with_the_requested_resource(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    service.get_transaction(customer_session, "TXN-001")

    event = _only(audit_sink)
    assert event.tool == "get_transaction"
    assert event.resource_type == "transaction"
    assert event.resource_id == "TXN-001"


def test_denied_call_is_audited(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    with pytest.raises(UnauthorizedResourceError):
        service.get_customer_context(customer_session, OTHER)

    event = _only(audit_sink)
    assert event.outcome == "denied"
    assert event.reason is Reason.UNAUTHORIZED_RESOURCE
    assert event.customer_id == OWNER
    assert event.resource_id == OTHER


def test_invalid_session_is_audited_without_a_customer(
    service: BankingService, audit_sink: InMemoryAuditSink
) -> None:
    with pytest.raises(InvalidSessionError):
        service.get_customer_transactions("unknown-session")

    event = _only(audit_sink)
    assert event.tool == "get_customer_transactions"
    assert event.outcome == "denied"
    assert event.reason is Reason.INVALID_SESSION
    assert event.customer_id is None
    assert event.session_fingerprint == fingerprint("unknown-session")


def test_expired_session_is_audited(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink, clock
) -> None:
    clock.advance(SESSION_TTL)

    with pytest.raises(ExpiredSessionError):
        service.get_transaction(customer_session, "TXN-001")

    event = _only(audit_sink)
    assert event.outcome == "denied"
    assert event.reason is Reason.EXPIRED_SESSION
    assert event.customer_id == OWNER


def test_missing_record_is_audited_as_not_found(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    with pytest.raises(TransactionNotFoundError):
        service.get_transaction(customer_session, "TXN-999")

    event = _only(audit_sink)
    assert event.outcome == "not_found"
    assert event.reason is Reason.TRANSACTION_NOT_FOUND


def test_verified_empty_result_is_audited_as_success(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    service.find_candidate_transactions(
        customer_session, CandidateFilters(transaction_status="Reversed")
    )

    assert _only(audit_sink).outcome == "success"


def test_unavailable_data_is_audited(
    service_without_data: BankingService, audit_sink: InMemoryAuditSink
) -> None:
    session = service_without_data.create_session(OWNER)

    with pytest.raises(DataUnavailableError):
        service_without_data.get_customer_context(session.session_id)

    event = _only(audit_sink)
    assert event.outcome == "failed"
    assert event.reason is Reason.DATA_UNAVAILABLE
    assert event.customer_id == OWNER


def test_every_tool_records_exactly_one_event(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    service.get_customer_context(customer_session)
    service.get_customer_transactions(customer_session, TransactionFilters(limit=1))
    service.get_transaction(customer_session, "TXN-001")
    service.find_candidate_transactions(customer_session, CandidateFilters(limit=1))
    service.verify_transaction_ownership(customer_session, "TXN-001")

    events = audit_sink.recent(limit=10)
    assert len(events) == 5
    assert [event.tool for event in events][::-1] == [
        "get_customer_context",
        "get_customer_transactions",
        "get_transaction",
        "find_candidate_transactions",
        "verify_transaction_ownership",
    ]


def test_audit_never_stores_the_session_identifier(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    service.get_customer_context(customer_session)
    service.get_customer_transactions(customer_session)

    events = audit_sink.recent(limit=10)
    serialised = "".join(event.model_dump_json() for event in events)

    assert customer_session not in serialised
    assert all(event.session_fingerprint == fingerprint(customer_session) for event in events)


def test_audit_events_carry_no_raw_pii(
    service: BankingService, customer_session: str, audit_sink: InMemoryAuditSink
) -> None:
    service.get_customer_context(customer_session)
    service.get_customer_transactions(customer_session)
    service.get_transaction(customer_session, "TXN-001")

    curated = set(CUSTOMERS.curated_columns) | set(PRODUCTS.curated_columns)
    serialised = "".join(event.model_dump_json() for event in audit_sink.recent(limit=10))
    candidates = [
        value
        for column, value in CUSTOMER_DEFAULTS.items()
        if column not in curated and len(value) >= 5
    ]

    assert [value for value in candidates if value in serialised] == []

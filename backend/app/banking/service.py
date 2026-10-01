import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from app.banking.audit import AuditEvent, AuditSink, fingerprint
from app.banking.errors import (
    BankingError,
    CustomerNotFoundError,
    InvalidRequestError,
    Outcome,
    Reason,
    TransactionNotFoundError,
    UnauthorizedResourceError,
)
from app.banking.models import (
    CandidateFilters,
    CandidateSearch,
    CustomerContext,
    CustomerTransactions,
    OwnershipVerification,
    TransactionFilters,
    TransactionRecord,
)
from app.banking.repository import CuratedBankingRepository
from app.banking.sessions import Session, SessionStore
from app.data.contracts import CHANNEL_DOMAIN, TRANSACTION_STATUS_DOMAIN, TRANSACTION_TYPE_DOMAIN

DOMAIN_FILTERS = {
    "transaction_type": TRANSACTION_TYPE_DOMAIN,
    "transaction_status": TRANSACTION_STATUS_DOMAIN,
    "channel": CHANNEL_DOMAIN,
}


class BankingService:
    """The banking tool layer.

    Every tool authenticates first, authorizes the authenticated customer against the resource,
    and records exactly one audit event. The customer a read is scoped to is always the session
    customer: a caller-supplied identifier is only ever checked, never trusted.
    """

    def __init__(
        self,
        repository: CuratedBankingRepository,
        sessions: SessionStore,
        audit: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        self._audit = audit
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    def create_session(self, customer_id: str) -> Session:
        return self._sessions.issue(customer_id)

    def recent_audit_events(self, limit: int) -> list[AuditEvent]:
        return self._audit.recent(limit)

    def get_customer_context(
        self, session_id: str | None, customer_id: str | None = None
    ) -> CustomerContext:
        with self._tool(
            "get_customer_context", session_id, "customer", customer_id
        ) as authenticated:
            subject = self._require_self(authenticated, customer_id)
            customer = self._repository.find_customer(subject)
            if customer is None:
                raise CustomerNotFoundError(f"no curated record for {subject}", customer_id=subject)
            return CustomerContext(
                customer=customer, products=self._repository.list_products(subject)
            )

    def get_customer_transactions(
        self,
        session_id: str | None,
        filters: TransactionFilters | None = None,
        customer_id: str | None = None,
    ) -> CustomerTransactions:
        with self._tool("get_customer_transactions", session_id, "customer", customer_id) as actor:
            subject = self._require_self(actor, customer_id)
            applied = self._validated(filters)
            return CustomerTransactions(
                customer_id=subject,
                filters=applied,
                transactions=self._repository.list_transactions(subject, applied),
            )

    def get_transaction(self, session_id: str | None, transaction_id: str) -> TransactionRecord:
        with self._tool(
            "get_transaction", session_id, "transaction", transaction_id
        ) as authenticated:
            identifier = self._require_identifier(transaction_id)
            record = self._repository.find_transaction(identifier)
            if record is None or not self._owns(authenticated, record.customer_id):
                # Absent and owned-by-someone-else collapse into one answer on purpose: a distinct
                # unauthorized error would confirm that the transaction id exists.
                raise TransactionNotFoundError(customer_id=authenticated)
            return record

    def find_candidate_transactions(
        self,
        session_id: str | None,
        filters: CandidateFilters | None = None,
        customer_id: str | None = None,
    ) -> CandidateSearch:
        with self._tool(
            "find_candidate_transactions", session_id, "customer", customer_id
        ) as authenticated:
            subject = self._require_self(authenticated, customer_id)
            applied = self._validated(filters)
            return CandidateSearch(
                customer_id=subject,
                filters=applied,
                candidates=self._repository.list_transactions(subject, applied),
            )

    def verify_transaction_ownership(
        self, session_id: str | None, transaction_id: str
    ) -> OwnershipVerification:
        with self._tool(
            "verify_transaction_ownership", session_id, "transaction", transaction_id
        ) as authenticated:
            identifier = self._require_identifier(transaction_id)
            record = self._repository.find_transaction(identifier)
            return OwnershipVerification(
                transaction_id=identifier,
                customer_id=authenticated,
                owned=record is not None and self._owns(authenticated, record.customer_id),
            )

    @contextmanager
    def _tool(
        self,
        action: str,
        session_id: str | None,
        resource_type: str,
        resource_id: str | None,
    ) -> Iterator[str]:
        started = time.perf_counter()
        outcome, reason = Outcome.FAILED, Reason.TOOL_FAILURE
        customer_id: str | None = None
        try:
            session = self._sessions.resolve(session_id)
            customer_id = session.customer_id
            yield session.customer_id
            outcome, reason = Outcome.SUCCESS, None
        except BankingError as exc:
            outcome, reason = exc.outcome, exc.reason
            customer_id = customer_id or exc.customer_id
            raise
        finally:
            self._audit.record(
                AuditEvent(
                    occurred_at=self._clock(),
                    tool=action,
                    outcome=outcome,
                    reason=reason,
                    customer_id=customer_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    session_fingerprint=fingerprint(session_id),
                )
            )

    @staticmethod
    def _require_self(authenticated: str, requested: str | None) -> str:
        if requested is None:
            return authenticated
        subject = requested.strip()
        if not subject:
            raise InvalidRequestError("customer identifier is empty", customer_id=authenticated)
        if subject != authenticated:
            raise UnauthorizedResourceError(
                f"session customer {authenticated} cannot act on {subject}",
                customer_id=authenticated,
            )
        return authenticated

    @staticmethod
    def _require_identifier(value: str) -> str:
        identifier = (value or "").strip()
        if not identifier:
            raise InvalidRequestError("transaction identifier is empty")
        return identifier

    @staticmethod
    def _owns(customer_id: str, owner_id: str) -> bool:
        return owner_id == customer_id

    def _validated(self, filters: TransactionFilters | None) -> TransactionFilters:
        applied = filters if filters is not None else TransactionFilters()
        for name, domain in DOMAIN_FILTERS.items():
            value = getattr(applied, name)
            if value is not None and value not in domain:
                raise InvalidRequestError(f"{name} is outside the recorded domain: {value!r}")

        if (
            applied.date_from is not None
            and applied.date_to is not None
            and applied.date_from > applied.date_to
        ):
            raise InvalidRequestError("date_from is after date_to")
        if (
            isinstance(applied, CandidateFilters)
            and applied.amount_min is not None
            and applied.amount_max is not None
            and applied.amount_min > applied.amount_max
        ):
            raise InvalidRequestError("amount_min is above amount_max")
        return applied

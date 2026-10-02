from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel

from app.api.dependencies import get_banking_service
from app.banking.audit import AuditEvent
from app.banking.errors import InvalidRequestError
from app.banking.models import (
    CandidateFilters,
    CandidateSearch,
    CustomerContext,
    CustomerTransactions,
    OwnershipVerification,
    TransactionFilters,
    TransactionRecord,
)
from app.banking.service import BankingService

router = APIRouter()

BankingServiceDep = Annotated[BankingService, Depends(get_banking_service)]
# The session travels in a header, never in a path or body, so a resource identifier can never be
# mistaken for proof of identity.
SessionHeader = Annotated[str | None, Header(alias="X-Session-Id")]

TRANSACTION_FILTER_KEYS = frozenset(
    {
        "transaction_type",
        "transaction_status",
        "channel",
        "currency",
        "date_from",
        "date_to",
        "limit",
    }
)
CANDIDATE_FILTER_KEYS = TRANSACTION_FILTER_KEYS | {"amount_min", "amount_max"}
# Accepted so the service, not the route, is what refuses a mismatched customer_id: the check has
# to live below the transport layer so future tools inherit it.
RESOURCE_SCOPE_KEY = "customer_id"
MAX_AUDIT_LIMIT = 200


class SessionRequest(BaseModel):
    customer_id: str


class SessionResponse(BaseModel):
    session_id: str
    customer_id: str
    issued_at: str
    expires_at: str


class AuditEventsResponse(BaseModel):
    events: list[AuditEvent]


def _query_values(request: Request, allowed: frozenset[str]) -> dict[str, str]:
    # Unsupported parameters are rejected rather than ignored: a silently dropped filter would
    # return records the caller did not ask for.
    unsupported = sorted(set(request.query_params) - allowed - {RESOURCE_SCOPE_KEY})
    if unsupported:
        raise InvalidRequestError(f"unsupported query parameters: {', '.join(unsupported)}")
    keys = allowed | {RESOURCE_SCOPE_KEY}
    return {key: request.query_params[key] for key in keys if key in request.query_params}


def _audit_limit(raw: str) -> int:
    try:
        limit = int(raw)
    except ValueError as exc:
        raise InvalidRequestError(f"limit is not an integer: {raw!r}") from exc
    if not 1 <= limit <= MAX_AUDIT_LIMIT:
        raise InvalidRequestError(f"limit must be between 1 and {MAX_AUDIT_LIMIT}")
    return limit


@router.post("/api/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def open_session(payload: SessionRequest, service: BankingServiceDep) -> SessionResponse:
    # Demo-only identity assertion: the caller states who it is and receives a session. No
    # credential is verified at this endpoint and none is in scope for this phase.
    session = service.create_session(payload.customer_id)
    return SessionResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
    )


@router.get("/api/customer/context", response_model=CustomerContext)
def own_customer_context(
    request: Request, service: BankingServiceDep, session_id: SessionHeader = None
) -> CustomerContext:
    # The same read as the customer-scoped route, addressed by the session alone. A caller that
    # already holds a session never has to learn or send a customer identifier to read its own
    # context, so no resource identifier can be replayed into a URL. Passing no customer_id means
    # the service authorizes against the authenticated customer itself; the self check still runs
    # below the transport layer. No query parameter is accepted at all, `customer_id` included, so
    # this route cannot be narrowed by a caller - the scoped routes tolerate that key on purpose,
    # but here there is nothing for it to narrow.
    if request.query_params:
        unsupported = ", ".join(sorted(request.query_params))
        raise InvalidRequestError(f"unsupported query parameters: {unsupported}")
    return service.get_customer_context(session_id, None)


@router.get("/api/customers/{customer_id}/context", response_model=CustomerContext)
def customer_context(
    customer_id: str, service: BankingServiceDep, session_id: SessionHeader = None
) -> CustomerContext:
    return service.get_customer_context(session_id, customer_id)


@router.get("/api/transactions", response_model=CustomerTransactions)
def customer_transactions(
    request: Request, service: BankingServiceDep, session_id: SessionHeader = None
) -> CustomerTransactions:
    values = _query_values(request, TRANSACTION_FILTER_KEYS)
    scope = values.pop(RESOURCE_SCOPE_KEY, None)
    return service.get_customer_transactions(session_id, TransactionFilters(**values), scope)


@router.get("/api/transactions/candidates", response_model=CandidateSearch)
def candidate_transactions(
    request: Request, service: BankingServiceDep, session_id: SessionHeader = None
) -> CandidateSearch:
    values = _query_values(request, CANDIDATE_FILTER_KEYS)
    scope = values.pop(RESOURCE_SCOPE_KEY, None)
    return service.find_candidate_transactions(session_id, CandidateFilters(**values), scope)


@router.get("/api/transactions/{transaction_id}", response_model=TransactionRecord)
def transaction(
    transaction_id: str, service: BankingServiceDep, session_id: SessionHeader = None
) -> TransactionRecord:
    return service.get_transaction(session_id, transaction_id)


@router.get("/api/transactions/{transaction_id}/ownership", response_model=OwnershipVerification)
def transaction_ownership(
    transaction_id: str, service: BankingServiceDep, session_id: SessionHeader = None
) -> OwnershipVerification:
    return service.verify_transaction_ownership(session_id, transaction_id)


@router.get("/api/audit/events", response_model=AuditEventsResponse)
def audit_events(request: Request, service: BankingServiceDep) -> AuditEventsResponse:
    # Demo-only operator view of the in-process audit buffer: identifiers and outcomes, never
    # record contents. It is unauthenticated and must not survive into a real deployment.
    limit = _audit_limit(request.query_params.get("limit", "50"))
    return AuditEventsResponse(events=service.recent_audit_events(limit))

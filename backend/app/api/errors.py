from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse

from app.banking.errors import BankingError, Reason

# The transport contract lives here and not in the domain: the banking tools only know reasons.
ERROR_STATUS: Mapping[Reason, int] = {
    Reason.INVALID_SESSION: 401,
    Reason.EXPIRED_SESSION: 401,
    Reason.UNAUTHORIZED_RESOURCE: 403,
    Reason.CUSTOMER_NOT_FOUND: 404,
    Reason.TRANSACTION_NOT_FOUND: 404,
    Reason.INCIDENT_NOT_FOUND: 404,
    Reason.CASE_NOT_FOUND: 404,
    Reason.INVALID_REQUEST: 400,
    Reason.DATA_UNAVAILABLE: 503,
    Reason.TOOL_FAILURE: 500,
}


async def banking_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, BankingError) else BankingError()
    return JSONResponse(
        status_code=ERROR_STATUS[error.reason],
        content={"error": error.reason.value, "message": error.message},
    )

from enum import StrEnum


class Reason(StrEnum):
    """Machine-readable failure classification carried to audit events and API responses."""

    INVALID_SESSION = "invalid_session"
    EXPIRED_SESSION = "expired_session"
    UNAUTHORIZED_RESOURCE = "unauthorized_resource"
    CUSTOMER_NOT_FOUND = "customer_not_found"
    TRANSACTION_NOT_FOUND = "transaction_not_found"
    INCIDENT_NOT_FOUND = "incident_not_found"
    CASE_NOT_FOUND = "case_not_found"
    INVALID_REQUEST = "invalid_request"
    DATA_UNAVAILABLE = "data_unavailable"
    TOOL_FAILURE = "tool_failure"


class Outcome(StrEnum):
    """How a banking tool call ended. SUCCESS covers verified empty results."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    DENIED = "denied"
    FAILED = "failed"


class BankingError(Exception):
    """A banking tool could not produce a verified result.

    `message` is the only text that may cross the API boundary; `detail` stays in-process for
    debugging and tests. Nothing derived from a database row, a SQL string or a filesystem path
    is allowed in `message`, so an error can never be used to confirm that a record exists.
    """

    reason: Reason = Reason.TOOL_FAILURE
    outcome: Outcome = Outcome.FAILED
    message: str = "The banking request could not be completed."

    def __init__(self, detail: str | None = None, *, customer_id: str | None = None) -> None:
        super().__init__(detail or self.message)
        self.detail = detail or self.message
        self.customer_id = customer_id


class InvalidSessionError(BankingError):
    reason = Reason.INVALID_SESSION
    outcome = Outcome.DENIED
    message = "Session is not valid."


class ExpiredSessionError(BankingError):
    reason = Reason.EXPIRED_SESSION
    outcome = Outcome.DENIED
    message = "Session has expired."


class UnauthorizedResourceError(BankingError):
    reason = Reason.UNAUTHORIZED_RESOURCE
    outcome = Outcome.DENIED
    message = "The requested resource does not belong to the authenticated customer."


class CustomerNotFoundError(BankingError):
    reason = Reason.CUSTOMER_NOT_FOUND
    outcome = Outcome.NOT_FOUND
    message = "Customer not found."


class TransactionNotFoundError(BankingError):
    reason = Reason.TRANSACTION_NOT_FOUND
    outcome = Outcome.NOT_FOUND
    # A transaction owned by another customer is reported with this exact message, so the tool
    # cannot be used to probe which transaction ids exist.
    message = "Transaction not found."


class IncidentNotFoundError(BankingError):
    reason = Reason.INCIDENT_NOT_FOUND
    outcome = Outcome.NOT_FOUND
    # An incident owned by another customer is reported with this exact message, so reading a
    # timeline cannot be used to probe which incident ids exist.
    message = "Incident not found."


class CaseNotFoundError(BankingError):
    reason = Reason.CASE_NOT_FOUND
    outcome = Outcome.NOT_FOUND
    message = "Case not found."


class InvalidRequestError(BankingError):
    reason = Reason.INVALID_REQUEST
    outcome = Outcome.FAILED
    message = "The request contains values this banking tool does not support."


class DataUnavailableError(BankingError):
    reason = Reason.DATA_UNAVAILABLE
    outcome = Outcome.FAILED
    message = "Banking data is unavailable."

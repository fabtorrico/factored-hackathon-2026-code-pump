from __future__ import annotations

from enum import StrEnum, unique


@unique
class IncidentLabel(StrEnum):
    """Customer-reported issue classes (semantic labels only)."""

    PENDING_OR_DELAYED = "PENDING_OR_DELAYED"
    FAILED_OR_DECLINED = "FAILED_OR_DECLINED"
    REVERSED = "REVERSED"
    APPROVED_BUT_UNRESOLVED = "APPROVED_BUT_UNRESOLVED"
    AMBIGUOUS_TRANSACTION = "AMBIGUOUS_TRANSACTION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


ALL_LABELS = tuple(IncidentLabel)

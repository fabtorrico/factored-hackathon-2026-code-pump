"""Demo entry point for the Phase 5A prototype.

Exposes the deterministic profile catalogue and opens a session from a profile id. The curated
customer identifier is resolved in-process and never appears in a request or a response, so the
prototype can offer a customer a realistic starting point without letting a caller choose which
curated customer it becomes.

Demo-only. Nothing here bypasses authentication: every other endpoint still requires the session
this one issues and still authorizes the same way it did before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_banking_service, get_demo_database_path
from app.banking.errors import InvalidRequestError
from app.banking.service import BankingService
from app.demo.profiles import DemoProfile, list_demo_profiles, resolve_demo_selection

router = APIRouter()

BankingServiceDep = Annotated[BankingService, Depends(get_banking_service)]
DatabasePathDep = Annotated[Path, Depends(get_demo_database_path)]


class DemoProfileResponse(BaseModel):
    """One selectable profile. Deliberately carries no customer identifier and no customer data."""

    model_config = ConfigDict(frozen=True)

    profile_id: str
    display_name: str
    scenario: str
    headline: str
    transaction_count: int
    highlight_status: str | None
    highlight_count: int
    prefill_filters: dict[str, str] | None


class DemoProfilesResponse(BaseModel):
    profiles: list[DemoProfileResponse]


class DemoSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, max_length=64)


class DemoSessionResponse(BaseModel):
    """The profile the session stands for. The customer it resolves to stays in-process."""

    session_id: str
    profile_id: str
    display_name: str
    issued_at: str
    expires_at: str


def _profile_response(profile: DemoProfile) -> DemoProfileResponse:
    return DemoProfileResponse(
        profile_id=profile.profile_id,
        display_name=profile.display_name,
        scenario=profile.scenario.value,
        headline=profile.headline,
        transaction_count=profile.transaction_count,
        highlight_status=profile.highlight_status,
        highlight_count=profile.highlight_count,
        prefill_filters=dict(profile.prefill_filters) if profile.prefill_filters else None,
    )


@router.get(
    "/api/demo/profiles",
    response_model=DemoProfilesResponse,
    summary="List the demo customer profiles this prototype can start from",
)
def demo_profiles(database_path: DatabasePathDep) -> DemoProfilesResponse:
    # Unauthenticated on purpose: the caller has no session yet, and this describes only curated
    # facts about transactions, never about a customer.
    profiles = list_demo_profiles(database_path)
    return DemoProfilesResponse(profiles=[_profile_response(profile) for profile in profiles])


@router.post(
    "/api/demo/sessions",
    response_model=DemoSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a session for one demo profile",
)
def open_demo_session(
    payload: DemoSessionRequest, service: BankingServiceDep, database_path: DatabasePathDep
) -> DemoSessionResponse:
    try:
        selection = resolve_demo_selection(database_path, payload.profile_id)
    except LookupError as exc:
        raise InvalidRequestError(f"unknown demo profile: {payload.profile_id}") from exc
    session = service.create_session(selection.customer_id)
    return DemoSessionResponse(
        session_id=session.session_id,
        profile_id=selection.profile.profile_id,
        display_name=selection.profile.display_name,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
    )

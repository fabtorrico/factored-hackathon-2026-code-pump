"""Read-only Human Agent Workspace endpoints.

Demo-only access through a separate agent session header. Nothing here mutates a case, moves money,
assigns work, adds notes or reads the curated banking database: the workspace only replays the
operational records the workflow already wrote.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel

from app.agent import AgentCaseDetail, AgentCaseSummary, AgentWorkspace
from app.api.dependencies import get_agent_workspace

router = APIRouter(prefix="/api/agent", tags=["agent"])

AgentWorkspaceDep = Annotated[AgentWorkspace, Depends(get_agent_workspace)]
# A distinct header from the customer session, so a customer credential can never authorize an
# agent read and the two surfaces cannot be confused.
AgentSessionHeader = Annotated[str | None, Header(alias="X-Agent-Session-Id")]


class AgentSessionResponse(BaseModel):
    agent_session_id: str
    display_name: str
    issued_at: str
    expires_at: str


class AgentCaseListResponse(BaseModel):
    cases: list[AgentCaseSummary]


@router.post(
    "/sessions",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a demo-only, read-only agent session",
)
def open_agent_session(workspace: AgentWorkspaceDep) -> AgentSessionResponse:
    session = workspace.open_session()
    return AgentSessionResponse(
        agent_session_id=session.agent_session_id,
        display_name=session.display_name,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
    )


@router.get(
    "/cases",
    response_model=AgentCaseListResponse,
    summary="List the persisted support cases waiting for a specialist",
)
def list_agent_cases(
    workspace: AgentWorkspaceDep, agent_session_id: AgentSessionHeader = None
) -> AgentCaseListResponse:
    return AgentCaseListResponse(cases=list(workspace.list_cases(agent_session_id)))


@router.get(
    "/cases/{case_id}",
    response_model=AgentCaseDetail,
    summary="Read one case, its persisted handoff and its recorded timeline",
)
def agent_case(
    case_id: str, workspace: AgentWorkspaceDep, agent_session_id: AgentSessionHeader = None
) -> AgentCaseDetail:
    return workspace.get_case(agent_session_id, case_id)

"""Read-only Human Agent Workspace over persisted operational cases.

Demo-only access: a separate in-process agent session gates the agent reads and is never a customer
session, so the two surfaces stay conceptually distinct. Nothing here can move money, change a case,
reach the curated banking tables or read anything the workflow did not already verify.
"""

from app.agent.sessions import AgentSession, AgentSessionStore
from app.agent.workspace import (
    AgentCaseDetail,
    AgentCaseSummary,
    AgentMovementSummary,
    AgentWorkspace,
)

__all__ = [
    "AgentCaseDetail",
    "AgentCaseSummary",
    "AgentMovementSummary",
    "AgentSession",
    "AgentSessionStore",
    "AgentWorkspace",
]

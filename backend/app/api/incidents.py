from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.dependencies import get_incident_workflow
from app.api.routes import SessionHeader
from app.workflow.models import IncidentInput, WorkflowEvent, WorkflowResult
from app.workflow.orchestrator import IncidentWorkflow

router = APIRouter()

IncidentWorkflowDep = Annotated[IncidentWorkflow, Depends(get_incident_workflow)]


class IncidentTimeline(BaseModel):
    """The recorded steps of one incident, in order."""

    incident_id: str
    events: list[WorkflowEvent]


@router.post(
    "/api/incidents",
    response_model=WorkflowResult,
    status_code=status.HTTP_200_OK,
    summary="Run one structured incident through the policy workflow",
)
def handle_incident(
    payload: IncidentInput, workflow: IncidentWorkflowDep, session_id: SessionHeader = None
) -> WorkflowResult:
    # Thin by design: the route passes the structured input and the session to the workflow and
    # returns its structured result. There is no natural-language input here, and no way to submit
    # a policy outcome, a rule, a transaction status or a customer identity.
    return workflow.handle(session_id, payload)


@router.get(
    "/api/incidents/{incident_id}/events",
    response_model=IncidentTimeline,
    summary="Read the recorded steps of an incident the authenticated customer raised",
)
def incident_timeline(
    incident_id: str, workflow: IncidentWorkflowDep, session_id: SessionHeader = None
) -> IncidentTimeline:
    # Read-only and owner-scoped inside the workflow: the session is resolved against the same
    # SessionStore the banking tools authenticate against, and an incident owned by anyone else is
    # indistinguishable from one that does not exist.
    events = workflow.timeline(session_id, incident_id)
    return IncidentTimeline(incident_id=incident_id, events=list(events))

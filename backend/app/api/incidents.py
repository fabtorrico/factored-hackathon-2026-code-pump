from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_incident_workflow
from app.api.routes import SessionHeader
from app.workflow.models import IncidentInput, WorkflowResult
from app.workflow.orchestrator import IncidentWorkflow

router = APIRouter()

IncidentWorkflowDep = Annotated[IncidentWorkflow, Depends(get_incident_workflow)]


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

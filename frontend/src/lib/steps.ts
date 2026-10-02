import type { WorkflowEvent, WorkflowEventType, WorkflowResult } from "../api/types";

/**
 * Maps the backend's recorded workflow events onto the steps a customer sees.
 *
 * The events are the source of truth for progress, and the mapping is deliberately literal: a step
 * is only ever shown as done because an event that means exactly that was recorded. The support
 * case step in particular keys off `support_case_verified`, never off
 * `support_case_creation_attempted`, so a write that could not be read back is never shown as an
 * opened case.
 */

export type StepState = "done" | "failed" | "pending";

export interface WorkflowStep {
  key: string;
  label: string;
  detail: string | null;
  state: StepState;
}

export function buildSteps(events: readonly WorkflowEvent[], result: WorkflowResult): WorkflowStep[] {
  const recorded = new Set(events.map((event) => event.event_type));
  const steps: WorkflowStep[] = [];

  steps.push(
    step(
      "identified",
      "We identified the movement you meant",
      recorded.has("transaction_verified") || recorded.has("candidate_search_completed"),
      recorded.has("candidate_search_completed") ? "Checked the movements you described." : null,
    ),
  );

  steps.push(
    step(
      "decided",
      "We applied the resolution policy",
      recorded.has("policy_evaluated"),
      `Rule ${result.policy_decision.policy_rule} produced ${result.policy_decision.outcome}.`,
    ),
  );

  steps.push(
    step(
      "case",
      "We opened a support case",
      recorded.has("support_case_verified"),
      result.support_case === null && result.failure !== null
        ? "We tried, but we could not confirm a case was created."
        : (result.support_case?.case_id ?? null),
    ),
  );

  steps.push(
    step(
      "outcome",
      outcomeStepLabel(result),
      result.status === "completed",
      result.failure === null ? null : "The request did not finish.",
    ),
  );

  return steps;
}

function outcomeStepLabel(result: WorkflowResult): string {
  if (result.failure !== null || result.status === "failed") {
    return "We stopped before finishing";
  }
  switch (result.policy_decision.outcome) {
    case "RESOLVE":
      return "We closed the question with what our records show";
    case "CLARIFY":
      return "We asked you to narrow it down";
    case "ESCALATE":
      return "We handed it to a specialist";
    case "ABSTAIN":
      return "We left it alone, as it is outside our decisions";
  }
}

function step(key: string, label: string, done: boolean, detail: string | null): WorkflowStep {
  return { key, label, detail, state: done ? "done" : "pending" };
}

/** The case step is the only one that can be explicitly marked as failed. */
export function markCaseStep(steps: WorkflowStep[], events: readonly WorkflowEvent[]): WorkflowStep[] {
  const failed = events.some((event) => event.event_type === "support_case_verification_failed");
  if (!failed) {
    return steps;
  }
  return steps.map((entry) =>
    entry.key === "case" ? { ...entry, state: "failed" as const, detail: null } : entry,
  );
}

/** Label for one event type, used by the timeline's detail rows. Never renders `detail` values. */
export function describeEvent(event: WorkflowEvent): string {
  const labels: Record<WorkflowEventType, string> = {
    incident_created: "Request received",
    candidate_search_completed: "Searched your movements",
    transaction_verified: "Movement verified",
    policy_evaluated: "Policy evaluated",
    support_case_creation_attempted: "Tried to open a support case",
    support_case_created: "Support case written",
    support_case_verified: "Support case confirmed",
    support_case_verification_failed: "Support case could not be confirmed",
    workflow_resolved: "Resolved",
    workflow_clarification_required: "Needs one more detail",
    workflow_escalated: "Escalated",
    workflow_abstained: "Left alone",
    banking_lookup_failed: "Could not read your records",
    workflow_failed: "Stopped",
  };
  return labels[event.event_type];
}
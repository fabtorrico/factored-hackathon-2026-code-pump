import { describe, expect, it } from "vitest";

import type { WorkflowEvent, WorkflowResult } from "../api/types";
import { buildSteps, describeEvent, markCaseStep } from "./steps";

/**
 * The step list is built from the events the backend recorded, so the risk is showing a step as
 * done because something *attempted* it. The support case step is the case in point.
 */

function event(type: WorkflowEvent["event_type"]): WorkflowEvent {
  return { incident_id: "INC-1", occurred_at: "2026-06-18T12:00:00Z", event_type: type, detail: {} };
}

function escalated(overrides: Partial<WorkflowResult> = {}): WorkflowResult {
  return {
    incident_id: "INC-1",
    status: "completed",
    created_at: "2026-06-18T12:00:00Z",
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "pending_status",
      policy_rule: "G_PENDING",
      policy_version: "1.0.0",
    },
    verified_transaction: null,
    clarification: null,
    support_case: {
      case_id: "CASE-1",
      incident_id: "INC-1",
      status: "open",
      recommended_route: "PAYMENTS_OPERATIONS",
      created_at: "2026-06-18T12:00:00Z",
    },
    handoff: null,
    failure: null,
    ...overrides,
  };
}

const ESCALATION_EVENTS: WorkflowEvent[] = [
  event("incident_created"),
  event("transaction_verified"),
  event("policy_evaluated"),
  event("support_case_creation_attempted"),
  event("support_case_created"),
  event("support_case_verified"),
  event("workflow_escalated"),
];

describe("the support case step needs a verification event, not an attempt", () => {
  it("is done once the case was verified", () => {
    const steps = buildSteps(ESCALATION_EVENTS, escalated());
    expect(steps.find((step) => step.key === "case")?.state).toBe("done");
  });

  it("is not done when only the attempt was recorded", () => {
    const attempted = ESCALATION_EVENTS.filter(
      (entry) => entry.event_type !== "support_case_verified" && entry.event_type !== "workflow_escalated",
    );
    const steps = buildSteps(attempted, escalated({ support_case: null, status: "failed" }));

    expect(steps.find((step) => step.key === "case")?.state).toBe("pending");
  });

  it("is marked failed when verification failed", () => {
    const events = [
      event("incident_created"),
      event("transaction_verified"),
      event("policy_evaluated"),
      event("support_case_creation_attempted"),
      event("support_case_verification_failed"),
      event("workflow_failed"),
    ];
    const failed = escalated({
      status: "failed",
      support_case: null,
      handoff: null,
      failure: { reason: "support_case_unverified" },
    });

    const steps = markCaseStep(buildSteps(events, failed), events);

    expect(steps.find((step) => step.key === "case")?.state).toBe("failed");
    expect(steps.find((step) => step.key === "outcome")?.state).toBe("pending");
  });
});

describe("every step reflects what was actually recorded", () => {
  it("marks identification done for a verified transaction", () => {
    const steps = buildSteps(ESCALATION_EVENTS, escalated());
    expect(steps.find((step) => step.key === "identified")?.state).toBe("done");
  });

  it("marks identification done for a candidate search", () => {
    const searchOnly = [event("incident_created"), event("candidate_search_completed"), event("policy_evaluated")];
    const clarify = escalated({
      policy_decision: {
        outcome: "CLARIFY",
        reason_code: "multiple_candidate_transactions",
        policy_rule: "D_MULTIPLE_CANDIDATES",
        policy_version: "1.0.0",
      },
      clarification: { reason: "multiple_candidate_transactions", candidates: [] },
      support_case: null,
    });

    const steps = buildSteps(searchOnly, clarify);

    expect(steps.find((step) => step.key === "identified")?.state).toBe("done");
    expect(steps.find((step) => step.key === "identified")?.detail).toBe("Checked the movements you described.");
  });

  it("describes the policy step without exposing the internal rule id", () => {
    const steps = buildSteps(ESCALATION_EVENTS, escalated());
    const detail = steps.find((step) => step.key === "decided")?.detail ?? "";
    expect(detail).not.toContain("G_PENDING");
    expect(detail).not.toContain("1.0.0");
    expect(detail.length).toBeGreaterThan(0);
  });

  it("confirms the case without repeating its long identifier", () => {
    const steps = buildSteps(ESCALATION_EVENTS, escalated());
    const detail = steps.find((step) => step.key === "case")?.detail ?? "";
    expect(detail).toBe("A support case was confirmed.");
    expect(detail).not.toContain("CASE-1");
  });
});

describe("event labels", () => {
  it("describes an attempted case without implying it succeeded", () => {
    expect(describeEvent(event("support_case_creation_attempted"))).toBe("Tried to open a support case");
    expect(describeEvent(event("support_case_verified"))).toBe("Support case confirmed");
    expect(describeEvent(event("support_case_verification_failed"))).toBe("Support case could not be confirmed");
  });

  it("has a label for every event the backend can record", () => {
    const every: WorkflowEvent["event_type"][] = [
      "incident_created",
      "candidate_search_completed",
      "transaction_verified",
      "policy_evaluated",
      "support_case_creation_attempted",
      "support_case_created",
      "support_case_verified",
      "support_case_verification_failed",
      "workflow_resolved",
      "workflow_clarification_required",
      "workflow_escalated",
      "workflow_abstained",
      "banking_lookup_failed",
      "workflow_failed",
    ];
    for (const type of every) {
      expect(describeEvent(event(type))).not.toBe("");
    }
  });
});
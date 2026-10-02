import type { AgentMovementSummary, HandoffFact, PolicyDecision } from "../api/types";
import { formatAmount, humanize, NOT_RECORDED } from "./format";
import type { OutcomeTone } from "./outcome";

/**
 * Display vocabulary for the Human Agent Workspace.
 *
 * This surface is allowed to be technical — a specialist can read rule ids and event codes — but it
 * is still total: an unknown code is shown as itself rather than hidden, and a missing value is
 * marked as missing. No fact is inferred and no customer identity exists here to begin with.
 */

/** A short, stable label for a case, so the queue does not lead with a 36-character id. */
export function caseReference(caseId: string | null | undefined): string {
  if (typeof caseId !== "string" || caseId === "") {
    return NOT_RECORDED;
  }
  const compact = caseId.replace(/[^a-zA-Z0-9]/g, "");
  return compact === "" ? NOT_RECORDED : `CASE ${compact.slice(0, 8).toUpperCase()}`;
}

export function describeFact(fact: HandoffFact): string {
  const labels: Record<string, string> = {
    authenticated_customer_verified: "Customer authenticated",
    banking_data_available: "Banking data available",
    transaction_ownership_verified: "Movement ownership verified",
    transaction_status: "Movement status",
    transaction_type: "Movement type",
    transaction_amount: "Amount",
    transaction_currency: "Currency",
    transaction_date: "Movement date",
    process_date: "Process date",
  };
  return labels[fact.fact] ?? humanize(fact.fact);
}

export function describeFactValue(fact: HandoffFact): string {
  if (fact.value === null || fact.value === "") {
    return "No value recorded";
  }
  if (fact.fact === "authenticated_customer_verified" || fact.fact === "banking_data_available" || fact.fact === "transaction_ownership_verified") {
    return fact.value === "true" ? "Yes" : "No";
  }
  return fact.value;
}

export function describeFactSource(source: string): string {
  const labels: Record<string, string> = {
    session: "Session",
    banking_core: "Banking core",
    workflow: "Workflow",
  };
  return labels[source] ?? humanize(source);
}

export function describeAction(action: string): string {
  const labels: Record<string, string> = {
    session_validated: "Validated the session",
    candidate_search_completed: "Searched for matching movements",
    transaction_verified: "Verified the movement",
    banking_lookup_failed: "Banking lookup failed",
    policy_evaluated: "Evaluated the resolution policy",
    support_case_created: "Wrote the support case",
    support_case_verified: "Read the support case back",
  };
  return labels[action] ?? humanize(action);
}

export function describeEvidence(kind: string): string {
  const labels: Record<string, string> = {
    transaction_response_code: "Recorded response code",
    transaction_amount_usd: "Amount in USD",
    transaction_process_date: "Process date",
  };
  return labels[kind] ?? humanize(kind);
}

/** An `unresolved_questions` code, restated as the open question it is. */
export function describeUnresolved(code: string): string {
  const labels: Record<string, string> = {
    banking_data_unavailable: "Banking data could not be read.",
    final_settlement_state_unavailable: "Settlement state is not available yet.",
    returned_funds_not_independently_verified: "Returned funds were not independently verified.",
    unresolved_issue_on_approved_transaction: "Approved movement with an issue still open.",
    unsupported_transaction_status_requires_review: "Unsupported status needs human review.",
    required_evidence_unavailable: "Required evidence is unavailable.",
  };
  return labels[code] ?? humanize(code);
}

export function describePolicyDecision(decision: PolicyDecision): string {
  return `${decision.policy_rule} produced ${decision.outcome} (reason ${decision.reason_code}).`;
}

export function movementAmount(movement: AgentMovementSummary): string {
  const amount = movement.amount === null ? null : Number(movement.amount);
  return formatAmount(amount, movement.currency);
}

/** Colour for an outcome pill on the agent surface. The label always carries the word too. */
export function outcomeTone(outcome: string | null): OutcomeTone {
  switch (outcome) {
    case "RESOLVE":
      return "positive";
    case "ESCALATE":
    case "CLARIFY":
      return "attention";
    default:
      return "neutral";
  }
}

import type { AgentMovementSummary, HandoffFact, PolicyDecision } from "../api/types";
import { formatAmount, humanize } from "./format";
import type { OutcomeTone } from "./outcome";

export { caseReference } from "./reference";

/**
 * Display vocabulary for the Human Agent Workspace.
 *
 * This surface is allowed to be technical — a specialist can read rule ids and event codes — but it
 * is still total: an unknown code is shown as itself rather than hidden, and a missing value is
 * marked as missing. No fact is inferred and no customer identity exists here to begin with.
 */

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

/**
 * The policy rule name as a plain-language category.
 *
 * A specialist can read `G_PENDING`, but a screen that only prints codes makes the reader memorise
 * them. These are fixed labels for the rules this build ships; an unknown rule still shows itself,
 * so nothing is hidden.
 */
export function describePolicyRule(rule: string): string {
  const labels: Record<string, string> = {
    A_INVALID_UNAUTHORIZED_WORKFLOW: "Safety and authorization rule",
    B_OUT_OF_SCOPE: "Scope rule",
    C_TOOL_FAILURE: "Tool-failure rule",
    D_NO_CANDIDATES: "No matching movement rule",
    D_MULTIPLE_CANDIDATES: "Multiple matching movements rule",
    E_REQUIRED_EVIDENCE_MISSING: "Required-evidence rule",
    F_DECLINED: "Declined-status rule",
    G_PENDING: "In-progress-status rule",
    H_REVERSED: "Reversed-status rule",
    I_APPROVED_UNRESOLVED: "Approved-with-open-issue rule",
    J_APPROVED_NO_INCIDENT: "Approved-without-supported-incident rule",
    K_UNKNOWN_STATUS: "Unsupported-status rule",
  };
  return labels[rule] ?? humanize(rule);
}

/**
 * The policy reason as the neutral state it describes.
 *
 * Every sentence restates what the workflow verified. None of them invents a cause, a settlement, or
 * a banking meaning the policy does not have.
 */
export function describePolicyReason(reason: string): string {
  const labels: Record<string, string> = {
    invalid_session: "the session was not valid",
    unauthorized: "the request was not authorized",
    out_of_scope: "the request is outside the supported scope",
    tool_failure_exhausted: "a required read could not be completed",
    required_evidence_missing: "required evidence was not available",
    no_matching_transaction: "no movement matched the description",
    multiple_candidate_transactions: "more than one movement matched the description",
    declined_status: "the movement was verified as declined",
    pending_status: "the movement was verified as still in progress",
    reversed_status: "the movement was verified as reversed",
    approved_unresolved_issue: "the movement was approved with an issue still open",
    approved_no_supported_incident: "the movement was approved with no supported incident",
    unknown_transaction_status: "the status is not supported by this policy version",
  };
  return labels[reason] ?? humanize(reason);
}

export function describePolicyDecision(decision: PolicyDecision): string {
  return `${describePolicyRule(decision.policy_rule)} decided the ${humanize(
    decision.outcome,
  )} outcome: ${describePolicyReason(decision.reason_code)}.`;
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

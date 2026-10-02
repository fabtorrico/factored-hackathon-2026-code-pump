/**
 * The subset of the backend contracts this prototype consumes.
 *
 * These mirror `backend/app/banking/models.py`, `backend/app/demo/profiles.py` and
 * `backend/app/workflow/models.py`. Every field is optional or nullable where the curated data can
 * genuinely be missing, because a missing fact must stay missing all the way to the screen.
 */

/** Machine-readable failure reasons from `backend/app/banking/errors.py`. */
export type Reason =
  | "invalid_session"
  | "expired_session"
  | "unauthorized_resource"
  | "customer_not_found"
  | "transaction_not_found"
  | "incident_not_found"
  | "case_not_found"
  | "invalid_request"
  | "data_unavailable"
  | "tool_failure";

export interface ErrorBody {
  error: Reason;
  message: string;
}

export interface DemoProfile {
  profile_id: string;
  display_name: string;
  scenario: string;
  headline: string;
  transaction_count: number;
  highlight_status: string | null;
  highlight_count: number;
  prefill_filters: Record<string, string> | null;
}

export interface DemoSession {
  session_id: string;
  profile_id: string;
  display_name: string;
  issued_at: string;
  expires_at: string;
}

export interface Customer {
  customer_id: string;
  customer_status: string;
  segment: string;
  country: string;
  detected_accent: string | null;
}

export interface Product {
  product_id: string;
  customer_id: string;
  product_type: string;
  product_status: string;
  currency: string;
  current_balance: number | null;
  opening_channel: string;
  has_linked_app: boolean;
}

export interface CustomerContext {
  customer: Customer;
  products: Product[];
}

export interface Transaction {
  transaction_id: string;
  customer_id: string;
  product_id: string;
  transaction_date: string;
  process_date: string;
  transaction_type: string;
  amount: number;
  currency: string;
  amount_usd: number | null;
  channel: string;
  transaction_status: string;
  response_code: string | null;
}

export interface CustomerTransactions {
  customer_id: string;
  transactions: Transaction[];
}

export type PolicyOutcome = "RESOLVE" | "CLARIFY" | "ESCALATE" | "ABSTAIN";
export type WorkflowStatus = "open" | "completed" | "failed";

export interface PolicyDecision {
  outcome: PolicyOutcome;
  reason_code: string;
  policy_rule: string;
  policy_version: string;
}

export interface ClarificationCandidate {
  transaction_id: string;
  transaction_status: string;
  transaction_type: string;
  amount: number;
  currency: string;
  transaction_date: string;
}

export interface Clarification {
  reason: "multiple_candidate_transactions" | "no_matching_transaction";
  candidates: ClarificationCandidate[];
}

export interface SupportCase {
  case_id: string;
  incident_id: string;
  status: "open";
  recommended_route: string;
  created_at: string;
}

export interface HandoffFact {
  fact: string;
  value: string | null;
  source: string;
}

/** The structured restatement of what the customer reported. */
export interface HandoffRequest {
  identification_mode: "exact_transaction" | "candidate_search";
  transaction_reference: string | null;
  filters: Record<string, string | number | null> | null;
  in_scope: boolean;
  approved_with_unresolved_issue: boolean;
}

export interface Handoff {
  case_id: string;
  incident_id: string;
  customer_request: HandoffRequest;
  verified_facts: HandoffFact[];
  actions_taken: string[];
  supporting_evidence: { kind: string; value: string }[];
  unresolved_questions: string[];
  policy_decision: PolicyDecision;
  recommended_route: string;
}

export interface WorkflowFailure {
  reason: "support_case_unverified";
}

export interface WorkflowResult {
  incident_id: string;
  status: WorkflowStatus;
  created_at: string;
  policy_decision: PolicyDecision;
  verified_transaction: Transaction | null;
  clarification: Clarification | null;
  support_case: SupportCase | null;
  handoff: Handoff | null;
  failure: WorkflowFailure | null;
}

export type WorkflowEventType =
  | "incident_created"
  | "candidate_search_completed"
  | "transaction_verified"
  | "policy_evaluated"
  | "support_case_creation_attempted"
  | "support_case_created"
  | "support_case_verified"
  | "support_case_verification_failed"
  | "workflow_resolved"
  | "workflow_clarification_required"
  | "workflow_escalated"
  | "workflow_abstained"
  | "banking_lookup_failed"
  | "workflow_failed";

export interface WorkflowEvent {
  incident_id: string;
  occurred_at: string;
  event_type: WorkflowEventType;
  detail: Record<string, string>;
}

export interface IncidentTimeline {
  incident_id: string;
  events: WorkflowEvent[];
}

/** Filters the curated read accepts. Empty values mean "not filtering on this". */
export interface TransactionFilters {
  transaction_type?: string;
  transaction_status?: string;
  channel?: string;
  currency?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}

/** Exactly one of these identifies the movement. Never both. */
export type IncidentInput =
  | { transaction_id: string; in_scope?: boolean; approved_with_unresolved_issue?: boolean }
  | { filters: TransactionFilters; in_scope?: boolean; approved_with_unresolved_issue?: boolean };

// --- Human Agent Workspace (Phase 5B) ---------------------------------------------------

/** A demo-only, read-only agent session. Never a customer session. */
export interface AgentSession {
  agent_session_id: string;
  display_name: string;
  issued_at: string;
  expires_at: string;
}

/** The movement as the persisted handoff recorded it, not a fresh banking lookup. */
export interface AgentMovementSummary {
  transaction_reference: string | null;
  transaction_type: string | null;
  transaction_status: string | null;
  amount: string | null;
  currency: string | null;
}

export interface AgentCaseSummary {
  case_id: string;
  incident_id: string;
  status: "open";
  workflow_status: WorkflowStatus | null;
  outcome: PolicyOutcome | null;
  reason_code: string | null;
  policy_rule: string | null;
  policy_version: string | null;
  recommended_route: string;
  created_at: string;
  has_handoff: boolean;
  movement: AgentMovementSummary;
  unresolved_count: number;
}

export interface AgentCaseList {
  cases: AgentCaseSummary[];
}

export interface AgentCaseDetail {
  case: AgentCaseSummary;
  handoff: Handoff | null;
  events: WorkflowEvent[];
}
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
  value: string;
  source: string;
}

export interface Handoff {
  case_id: string;
  incident_id: string;
  verified_facts: HandoffFact[];
  actions_taken: string[];
  supporting_evidence: { kind: string; value: string }[];
  unresolved_questions: string[];
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
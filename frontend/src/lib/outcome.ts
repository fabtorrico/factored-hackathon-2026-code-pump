import type { Transaction, WorkflowResult } from "../api/types";

/**
 * Turns a `WorkflowResult` into the words the customer reads.
 *
 * This is the one place where the prototype could quietly start lying, so the rules are narrow:
 *
 * - Every sentence is derived from a field the backend actually returned. A status-specific
 *   sentence is emitted only when the verified transaction actually carries that status.
 * - Nothing here explains *why* a movement was declined. The curated `response_code` has no
 *   documented meaning, so a cause is never written; the recorded status is restated instead.
 * - "Pending" is described as unconfirmed, never as settled. "Reversed" is described as reversed,
 *   never as refunded, because the backend reports `returned_funds_not_independently_verified`.
 * - A failed verification never says a support case was created. The backend returns
 *   `status: "failed"` with no `support_case`, and the copy has to say so.
 * - An abstention is not dressed up as an answer.
 */

export type OutcomeTone = "positive" | "attention" | "neutral" | "critical";

export interface OutcomePresentation {
  /** Short label for the outcome pill. */
  label: string;
  tone: OutcomeTone;
  /** The headline the customer reads first. */
  headline: string;
  /** The sentences under it. Each one is grounded in a returned field. */
  paragraphs: string[];
  /** True only when the backend confirmed a support case exists. */
  caseOpened: boolean;
  /** True when a case was attempted but could not be verified. */
  caseUnverified: boolean;
  /** Facts the customer would otherwise have to guess. */
  caveats: string[];
}

/**
 * Claims that must never be made about a movement in this status.
 *
 * Matched with word boundaries, because "limit" inside "unlimited" is not a claim about a limit.
 */
const FORBIDDEN_FOR: Partial<Record<string, RegExp[]>> = {
  // The copy deliberately avoids these words entirely rather than negating them, so that the check
  // below stays a trustworthy, reviewable assertion instead of a negation-aware parser.
  pending: [/\bsettled\b/i, /\bcompleted\b/i, /\barrived\b/i, /\bfinal\b/i],
  reversed: [/\brefunded\b/i, /\bmoney is back\b/i, /\breturned to your account\b/i, /\breimbursed\b/i],
  declined: [/\binsufficient funds\b/i, /\blimit\b/i, /\bfraud\b/i, /\bbecause\b/i],
};

function sentences(...parts: (string | null | undefined)[]): string[] {
  return parts.filter((part): part is string => typeof part === "string" && part.trim() !== "");
}

export function presentOutcome(result: WorkflowResult): OutcomePresentation {
  if (result.status === "failed" || result.failure !== null) {
    return presentFailure(result);
  }
  const outcome = result.policy_decision.outcome;
  if (outcome === "CLARIFY") {
    return presentClarification(result);
  }
  if (outcome === "ABSTAIN") {
    return presentAbstention(result);
  }
  if (outcome === "RESOLVE") {
    return presentResolution(result);
  }
  return presentEscalation(result);
}

function presentFailure(result: WorkflowResult): OutcomePresentation {
  // The workflow could not confirm its own write, so the only honest statement is that we cannot
  // confirm anything. `support_case` is null here, and the copy must not imply otherwise. A failure
  // reason this build does not know still gets copy that claims nothing.
  const unverifiedCase = result.failure?.reason === "support_case_unverified";
  return {
    label: "Not completed",
    tone: "critical",
    headline: unverifiedCase
      ? "We could not confirm that this was escalated."
      : "This request did not finish.",
    paragraphs: sentences(
      unverifiedCase
        ? "The system recorded that it tried to open a support case but could not read the case back, so it cannot confirm that a case exists."
        : "The request stopped partway through, so we cannot tell you what was done.",
      "Please do not assume this has been handed to a specialist. Contact support quoting this reference if you are still waiting.",
    ),
    caseOpened: false,
    caseUnverified: true,
    caveats: [unverifiedCase ? "No support case was confirmed." : "The outcome of this request is unknown."],
  };
}

function presentClarification(result: WorkflowResult): OutcomePresentation {
  const candidates = result.clarification?.candidates ?? [];
  const noun = candidates.length === 1 ? "movement" : "movements";
  return {
    label: "We need one more detail",
    tone: "attention",
    headline: `We found ${candidates.length} ${noun} that ${candidates.length === 1 ? "matches" : "match"} what you described.`,
    paragraphs: sentences(
      candidates.length > 1
        ? "Nothing has been decided yet. Choose the one you meant and we will check exactly that movement."
        : "No movement of yours matches what you described, so nothing has been decided.",
    ),
    caseOpened: false,
    caseUnverified: false,
    caveats: ["No action has been taken on your account."],
  };
}

function presentAbstention(result: WorkflowResult): OutcomePresentation {
  const reason = result.policy_decision.reason_code;

  if (reason === "approved_no_supported_incident") {
    // The policy abstained because an approved movement with nothing outstanding is not an incident
    // this service handles. Saying only "not something we can decide here" would leave the customer
    // with no way forward, so the verified fact is stated and a real next step is offered. Approved is
    // what our records say about the movement; it is not a promise about where the money is.
    return {
      label: "Nothing to escalate",
      tone: "neutral",
      headline: "Our records show this movement was approved, with no unresolved issue on it.",
      paragraphs: sentences(
        "We did not open an incident for it, because an approved movement with nothing outstanding is not something this service escalates.",
        "If something about it still does not look right to you, please contact support quoting this reference.",
      ),
      caseOpened: false,
      caseUnverified: false,
      caveats: [],
    };
  }

  return {
    label: "Outside what we can decide",
    tone: "neutral",
    headline: "This is not something we can decide here.",
    paragraphs: sentences(
      reason === "invalid_session"
        ? "We could not confirm who you are from this request, so no records were read."
        : "This request is outside the decisions this service is allowed to make, so we did not act on it.",
    ),
    caseOpened: false,
    caseUnverified: false,
    caveats: [],
  };
}

function presentResolution(result: WorkflowResult): OutcomePresentation {
  const status = result.verified_transaction?.transaction_status ?? null;
  if (status === "Declined") {
    // The recorded status is the whole answer. A cause is not available and is not invented.
    return {
      label: "Resolved",
      tone: "positive",
      headline: "This movement was declined and the record is final.",
      paragraphs: sentences(
        "Our records show this movement was declined. We do not hold a reason for the decline, and we will not guess at one.",
        "The recorded status resolves your question, so there is nothing further pending from us on this movement.",
      ),
      caseOpened: false,
      caseUnverified: false,
      caveats: [],
    };
  }
  return {
    label: "Resolved",
    tone: "positive",
    headline: "The recorded status resolves this request.",
    paragraphs: sentences(
      status === null
        ? "No single movement was identified, so nothing specific was resolved."
        : `Our records show this movement as ${status}.`,
    ),
    caseOpened: false,
    caseUnverified: false,
    caveats: [],
  };
}

function presentEscalation(result: WorkflowResult): OutcomePresentation {
  const transaction = result.verified_transaction;
  const status = transaction?.transaction_status ?? null;
  const caseOpened = result.support_case !== null && result.handoff !== null;
  const unresolved = result.handoff?.unresolved_questions ?? [];

  const state = describeUnresolvedState(status, result.policy_decision.reason_code);
  const paragraphs = sentences(
    state,
    caseOpened
      ? "A support case has been opened with our payments operations team and the reference is below."
      : "We could not open a support case, so this has not been handed to a specialist.",
    // Anything the backend could not verify is stated as a limit, not resolved by wording.
    unresolved.map(toCaveatSentence).join(" ") || null,
  );

  return {
    label: caseOpened ? "Escalated" : "Needs a specialist",
    tone: "attention",
    headline: escalationHeadline(status),
    paragraphs,
    caseOpened,
    caseUnverified: false,
    caveats: unresolved.map(toCaveatSentence),
  };
}

/**
 * The verified status, restated without interpretation.
 *
 * "Pending" becomes unconfirmed, never settled. "Reversed" becomes reversed, never refunded.
 * An approved movement whose issue is still open stays open.
 */
function describeUnresolvedState(status: string | null, reasonCode: string): string | null {
  if (status === "Pending") {
    return "Our records show this movement is still in progress. We cannot confirm the outcome yet.";
  }
  if (status === "Reversed") {
    return "Our records show this movement was reversed. We have not confirmed that any money reached your account.";
  }
  if (reasonCode === "approved_unresolved_issue") {
    return "Our records show this movement was approved, and the issue you reported is still open.";
  }
  return status === null ? null : `Our records show this movement as ${status}.`;
}

function escalationHeadline(status: string | null): string {
  if (status === "Pending") {
    return "This movement is still in progress, so it needs a specialist.";
  }
  if (status === "Reversed") {
    return "This movement was reversed, so it needs a specialist.";
  }
  if (status === "Approved") {
    return "This movement went through, but your issue is still open.";
  }
  return "This needs a specialist.";
}

/** An `unresolved_questions` code, phrased as the limit it is. */
function toCaveatSentence(code: string): string {
  switch (code) {
    case "final_settlement_state_unavailable":
      return "Settlement state is not available to us yet.";
    case "returned_funds_not_independently_verified":
      return "We have not independently verified that funds returned to you.";
    case "unresolved_issue_on_approved_transaction":
      return "The movement is recorded as approved, but the issue is not closed.";
    default:
      return "There is a detail we could not verify.";
  }
}

/**
 * A guard used by the tests: given a result, return the sentences that would claim more than the
 * backend proved. Empty means the copy is safe for that result.
 */
export function unsupportedClaims(result: WorkflowResult): string[] {
  const text = presentOutcome(result).paragraphs.join(" ").toLowerCase();
  const status = result.verified_transaction?.transaction_status ?? null;
  const key = status === null ? undefined : status.toLowerCase();
  const banned = (key !== undefined ? FORBIDDEN_FOR[key] : undefined) ?? [];
  return banned.filter((claim) => claim.test(text)).map((claim) => claim.source);
}

/** The transaction a result verified, if any. Used to link back from the resolution center. */
export function verifiedTransaction(result: WorkflowResult): Transaction | null {
  return result.verified_transaction;
}
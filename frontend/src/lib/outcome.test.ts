import { describe, expect, it } from "vitest";

import type { WorkflowResult } from "../api/types";
import { presentOutcome, unsupportedClaims } from "./outcome";

/**
 * The outcome copy is where this prototype could quietly start lying, so these tests pin the
 * specific claims that must never appear for a given recorded status.
 *
 * Every fixture is shaped like a payload the backend actually returns for the curated data:
 * a declined withdrawal, a pending purchase, a reversed payment, an approved movement with an
 * unresolved issue, an ambiguous search, and a support case whose read-back failed.
 */

function transaction(overrides: Partial<WorkflowResult["verified_transaction"]> = {}) {
  return {
    transaction_id: "TRX-1",
    customer_id: "CLI-1",
    product_id: "PRD-1",
    transaction_date: "2026-06-17T06:35:58",
    process_date: "2026-06-17T00:00:00",
    transaction_type: "Payment",
    amount: 345.41,
    currency: "USD",
    amount_usd: null,
    channel: "App",
    transaction_status: "Declined",
    response_code: "51",
    ...overrides,
  } as NonNullable<WorkflowResult["verified_transaction"]>;
}

function result(overrides: Partial<WorkflowResult> = {}): WorkflowResult {
  return {
    incident_id: "INC-1",
    status: "completed",
    created_at: "2026-06-18T12:00:00Z",
    policy_decision: {
      outcome: "RESOLVE",
      reason_code: "declined_status",
      policy_rule: "F_DECLINED",
      policy_version: "1.0.0",
    },
    verified_transaction: transaction(),
    clarification: null,
    support_case: null,
    handoff: null,
    failure: null,
    ...overrides,
  };
}

function handoff(overrides: Partial<NonNullable<WorkflowResult["handoff"]>> = {}) {
  return {
    case_id: "CASE-1",
    incident_id: "INC-1",
    verified_facts: [],
    actions_taken: [],
    supporting_evidence: [],
    unresolved_questions: [],
    recommended_route: "PAYMENTS_OPERATIONS",
    ...overrides,
  } as NonNullable<WorkflowResult["handoff"]>;
}

describe("a declined movement resolves without inventing a cause", () => {
  const shown = presentOutcome(
    result({ verified_transaction: transaction({ transaction_status: "Declined" }) }),
  );

  it("states the recorded status", () => {
    expect(shown.headline).toContain("declined");
    expect(shown.tone).toBe("positive");
  });

  it("never explains why", () => {
    // `response_code` is "51" here. The curated data has no documented meaning for it.
    expect(unsupportedClaims(result())).toEqual([]);
    expect(shown.paragraphs.join(" ")).not.toMatch(/insufficient|limit|fraud|because/i);
  });

  it("does not claim a support case", () => {
    expect(shown.caseOpened).toBe(false);
  });
});

describe("an approved movement with nothing outstanding", () => {
  // The live backend abstains here (J_APPROVED_NO_INCIDENT) rather than resolving. The generic
  // "not something we can decide" copy would leave the customer with no way forward.
  const abstained = presentOutcome(
    result({
      policy_decision: {
        outcome: "ABSTAIN",
        reason_code: "approved_no_supported_incident",
        policy_rule: "J_APPROVED_NO_INCIDENT",
        policy_version: "1.0.0",
      },
      verified_transaction: transaction({ transaction_status: "Approved" }),
    }),
  );

  it("states only what the record says", () => {
    expect(abstained.headline).toMatch(/approved/i);
    expect(abstained.headline).not.toMatch(/arrived|in your account|settled|received/i);
  });

  it("says plainly that no incident was opened", () => {
    expect(abstained.paragraphs.join(" ")).toMatch(/did not open an incident/i);
    expect(abstained.caseOpened).toBe(false);
  });

  it("still gives the customer a way forward", () => {
    expect(abstained.paragraphs.join(" ")).toMatch(/contact support/i);
    // The reference lives in the page header, so the copy must not point at a position.
    expect(abstained.paragraphs.join(" ")).not.toMatch(/reference (below|above)/i);
  });
});

describe("an abstention for a reason this build does not know", () => {
  it("claims nothing specific", () => {
    const shown = presentOutcome(
      result({
        policy_decision: {
          outcome: "ABSTAIN",
          reason_code: "some_reason_from_a_later_release",
          policy_rule: "Z_SOMETHING",
          policy_version: "1.0.0",
        },
        verified_transaction: null,
      }),
    );

    expect(shown.headline).toMatch(/not something we can decide/i);
    expect(shown.paragraphs.join(" ")).not.toMatch(/approved|declined|pending|reversed/i);
  });
});

describe("a pending movement escalates without claiming it settled", () => {
  const pending = result({
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "pending_status",
      policy_rule: "G_PENDING",
      policy_version: "1.0.0",
    },
    verified_transaction: transaction({ transaction_status: "Pending", response_code: null }),
    support_case: {
      case_id: "CASE-1",
      incident_id: "INC-1",
      status: "open",
      recommended_route: "PAYMENTS_OPERATIONS",
      created_at: "2026-06-18T12:00:00Z",
    },
    handoff: handoff({ unresolved_questions: ["final_settlement_state_unavailable"] }),
  });

  it("says it has not settled", () => {
    expect(presentOutcome(pending).headline).toContain("still in progress");
    expect(unsupportedClaims(pending)).toEqual([]);
  });

  it("surfaces the unverified settlement as a caveat", () => {
    const shown = presentOutcome(pending);
    expect(shown.caveats).toContain("Settlement state is not available to us yet.");
    expect(shown.caseOpened).toBe(true);
  });
});

describe("a reversed movement escalates without claiming a refund", () => {
  const reversed = result({
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "reversed_status",
      policy_rule: "H_REVERSED",
      policy_version: "1.0.0",
    },
    verified_transaction: transaction({ transaction_status: "Reversed" }),
    support_case: {
      case_id: "CASE-1",
      incident_id: "INC-1",
      status: "open",
      recommended_route: "PAYMENTS_OPERATIONS",
      created_at: "2026-06-18T12:00:00Z",
    },
    handoff: handoff({ unresolved_questions: ["returned_funds_not_independently_verified"] }),
  });

  it("does not say the money came back", () => {
    expect(unsupportedClaims(reversed)).toEqual([]);
  });

  it("says the reversal is not a confirmation of returned funds", () => {
    const shown = presentOutcome(reversed);
    expect(shown.paragraphs.join(" ")).toContain("not confirmed");
    expect(shown.caveats).toContain("We have not independently verified that funds returned to you.");
  });
});

describe("an approved movement with an unresolved issue stays open", () => {
  const approved = result({
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "approved_unresolved_issue",
      policy_rule: "I_APPROVED_UNRESOLVED",
      policy_version: "1.0.0",
    },
    verified_transaction: transaction({ transaction_status: "Approved" }),
    support_case: {
      case_id: "CASE-1",
      incident_id: "INC-1",
      status: "open",
      recommended_route: "PAYMENTS_OPERATIONS",
      created_at: "2026-06-18T12:00:00Z",
    },
    handoff: handoff({ unresolved_questions: ["unresolved_issue_on_approved_transaction"] }),
  });

  it("does not present it as resolved", () => {
    const shown = presentOutcome(approved);
    expect(shown.label).toBe("Escalated");
    expect(shown.headline).toContain("still open");
  });
});

describe("a clarification decides nothing", () => {
  const clarify = result({
    policy_decision: {
      outcome: "CLARIFY",
      reason_code: "multiple_candidate_transactions",
      policy_rule: "D_MULTIPLE_CANDIDATES",
      policy_version: "1.0.0",
    },
    verified_transaction: null,
    clarification: {
      reason: "multiple_candidate_transactions",
      candidates: [
        { transaction_id: "A", transaction_status: "Approved", transaction_type: "Transfer", amount: 1, currency: "USD", transaction_date: "2026-06-17T00:00:00" },
        { transaction_id: "B", transaction_status: "Declined", transaction_type: "Transfer", amount: 2, currency: "USD", transaction_date: "2026-06-17T00:00:00" },
      ],
    },
  });

  it("asks for one more detail and claims nothing about the account", () => {
    const shown = presentOutcome(clarify);
    expect(shown.tone).toBe("attention");
    expect(shown.headline).toContain("2 movements");
    expect(shown.paragraphs.join(" ")).toContain("Nothing has been decided yet");
    expect(shown.caseOpened).toBe(false);
  });

  it("handles a single surviving candidate without claiming to match it", () => {
    const single = result({
      policy_decision: {
        outcome: "CLARIFY",
        reason_code: "multiple_candidate_transactions",
        policy_rule: "D_MULTIPLE_CANDIDATES",
        policy_version: "1.0.0",
      },
      verified_transaction: null,
      clarification: { reason: "multiple_candidate_transactions", candidates: [] },
    });
    expect(presentOutcome(single).paragraphs.join(" ")).toContain("No movement of yours matches");
  });
});

describe("an abstention is not dressed up as an answer", () => {
  it("reports an unusable session without reading anything", () => {
    const abstain = result({
      policy_decision: {
        outcome: "ABSTAIN",
        reason_code: "invalid_session",
        policy_rule: "Z_NO_SESSION",
        policy_version: "1.0.0",
      },
      verified_transaction: null,
    });

    const shown = presentOutcome(abstain);
    expect(shown.tone).toBe("neutral");
    expect(shown.paragraphs.join(" ")).toContain("could not confirm who you are");
    expect(shown.caveats).toEqual([]);
  });

  it("reports an out-of-scope request as undecided", () => {
    const abstain = result({
      policy_decision: {
        outcome: "ABSTAIN",
        reason_code: "out_of_scope",
        policy_rule: "Y_OUT_OF_SCOPE",
        policy_version: "1.0.0",
      },
    });

    const shown = presentOutcome(abstain);
    expect(shown.paragraphs.join(" ")).toContain("outside the decisions this service is allowed");
    expect(shown.label).not.toBe("Resolved");
  });
});

describe("a support case that could not be verified is never reported as opened", () => {
  const failed = result({
    status: "failed",
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "pending_status",
      policy_rule: "G_PENDING",
      policy_version: "1.0.0",
    },
    verified_transaction: transaction({ transaction_status: "Pending" }),
    support_case: null,
    handoff: null,
    failure: { reason: "support_case_unverified" },
  });

  const shown = presentOutcome(failed);

  it("says the escalation is unconfirmed", () => {
    expect(shown.label).toBe("Not completed");
    expect(shown.tone).toBe("critical");
    expect(shown.caseOpened).toBe(false);
    expect(shown.caseUnverified).toBe(true);
  });

  it("tells the customer not to assume a case exists", () => {
    const text = [shown.headline, ...shown.paragraphs].join(" ");
    expect(text).toContain("do not assume");
    expect(text).not.toMatch(/has been opened|was created|case has been/);
  });

  it("never states a settlement claim for a failed request", () => {
    expect(unsupportedClaims(failed)).toEqual([]);
  });
});

describe("escalation copy degrades safely when nothing was verified", () => {
  it("does not invent a movement when none is verified", () => {
    const escalate = result({
      policy_decision: {
        outcome: "ESCALATE",
        reason_code: "pending_status",
        policy_rule: "G_PENDING",
        policy_version: "1.0.0",
      },
      verified_transaction: null,
      support_case: {
        case_id: "CASE-1",
        incident_id: "INC-1",
        status: "open",
        recommended_route: "PAYMENTS_OPERATIONS",
        created_at: "2026-06-18T12:00:00Z",
      },
      handoff: handoff(),
    });

    const shown = presentOutcome(escalate);
    expect(shown.headline).toBe("This needs a specialist.");
    expect(shown.paragraphs.join(" ")).not.toContain("Our records show");
  });

  it("does not claim a case was opened when the backend returned none", () => {
    const escalate = result({
      policy_decision: {
        outcome: "ESCALATE",
        reason_code: "pending_status",
        policy_rule: "G_PENDING",
        policy_version: "1.0.0",
      },
      verified_transaction: transaction({ transaction_status: "Pending" }),
      support_case: null,
      handoff: handoff(),
    });

    const shown = presentOutcome(escalate);
    expect(shown.caseOpened).toBe(false);
    expect(shown.paragraphs.join(" ")).toContain("has not been handed to a specialist");
  });
});
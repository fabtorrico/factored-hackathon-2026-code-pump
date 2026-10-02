import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useEffect } from "react";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { IncidentTimeline, WorkflowResult } from "../api/types";
import { IncidentProvider, useIncidents } from "../state/IncidentProvider";
import { SessionProvider } from "../state/SessionProvider";
import { ResolutionView } from "./ResolutionView";

/**
 * Renders the real resolution view against a stubbed fetch, so the copy that reaches the screen is
 * checked end to end rather than only as a returned object.
 *
 * The payloads are the ones the backend actually returns for the curated data: a pending movement
 * whose support case verified, and one whose case could not be read back.
 */

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const PENDING: WorkflowResult = {
  incident_id: "INC-1",
  status: "completed",
  created_at: "2026-06-18T12:00:00Z",
  policy_decision: {
    outcome: "ESCALATE",
    reason_code: "pending_status",
    policy_rule: "G_PENDING",
    policy_version: "1.0.0",
  },
  verified_transaction: {
    transaction_id: "TRX-1",
    customer_id: "CLI-1",
    product_id: "PRD-1",
    transaction_date: "2026-06-17T06:35:58",
    process_date: "2026-06-17T00:00:00",
    transaction_type: "Purchase",
    amount: 345.41,
    currency: "USD",
    amount_usd: null,
    channel: "ATM",
    transaction_status: "Pending",
    response_code: null,
  },
  clarification: null,
  support_case: {
    case_id: "45105b30-e998-4531-8c2a-2cfe28ff27e0",
    incident_id: "INC-1",
    status: "open",
    recommended_route: "PAYMENTS_OPERATIONS",
    created_at: "2026-06-18T12:00:00Z",
  },
  handoff: {
    case_id: "CASE-1",
    incident_id: "INC-1",
    customer_request: {
      identification_mode: "exact_transaction",
      transaction_reference: "TRX-1",
      filters: null,
      in_scope: true,
      approved_with_unresolved_issue: false,
    },
    verified_facts: [],
    actions_taken: [],
    supporting_evidence: [],
    unresolved_questions: ["final_settlement_state_unavailable"],
    policy_decision: {
      outcome: "ESCALATE",
      reason_code: "pending_status",
      policy_rule: "G_PENDING",
      policy_version: "1.0.0",
    },
    recommended_route: "PAYMENTS_OPERATIONS",
  },
  failure: null,
};

function timeline(incidentId: string, types: string[]): IncidentTimeline {
  return {
    incident_id: incidentId,
    events: types.map((event_type) => ({
      incident_id: incidentId,
      occurred_at: "2026-06-18T12:00:00Z",
      event_type,
      detail: {},
    })),
  } as IncidentTimeline;
}

const ESCALATED = timeline("INC-1", [
  "incident_created",
  "transaction_verified",
  "policy_evaluated",
  "support_case_creation_attempted",
  "support_case_created",
  "support_case_verified",
  "workflow_escalated",
]);

const VERIFICATION_FAILED = timeline("INC-2", [
  "incident_created",
  "transaction_verified",
  "policy_evaluated",
  "support_case_creation_attempted",
  "support_case_verification_failed",
  "workflow_failed",
]);

/** Puts a result in the store on mount, the way submitting a report does. */
function Seed({ result }: { result: WorkflowResult }) {
  const { record } = useIncidents();
  useEffect(() => {
    record(result);
  }, [record, result]);
  return null;
}

function renderAt(incidentId: string, seed: WorkflowResult | null, events: IncidentTimeline) {
  const routes: Record<string, unknown> = {
    "/api/demo/profiles": { profiles: [] },
    [`/api/incidents/${incidentId}/events`]: events,
  };

  vi.stubGlobal(
    "fetch",
    ((url: string) => {
      const body = routes[url];
      const payload =
        body === undefined
          ? { error: "incident_not_found", message: "Incident not found." }
          : body;
      const status = body === undefined ? 404 : 200;
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch,
  );

  render(
    <MemoryRouter initialEntries={[`/resolution/${incidentId}`]}>
      <SessionProvider>
        <IncidentProvider>
          {seed !== null && <Seed result={seed} />}
          <Routes>
            <Route path="/resolution/:incidentId" element={<ResolutionView />} />
          </Routes>
        </IncidentProvider>
      </SessionProvider>
    </MemoryRouter>,
  );
}

describe("an escalation whose support case verified", () => {
  it("says the movement is still in progress and never claims it settled", async () => {
    renderAt("INC-1", PENDING, ESCALATED);

    expect((await screen.findAllByText(/still in progress/i)).length).toBeGreaterThan(0);
    expect(screen.getByText(/cannot confirm the outcome/i)).toBeTruthy();
    expect(screen.queryByText(/has settled/i)).toBeNull();
    expect(screen.queryByText(/completed the payment/i)).toBeNull();
  });

  it("lists what it could not verify", async () => {
    renderAt("INC-1", PENDING, ESCALATED);

    // The caveat appears twice on purpose: once in the narrative and once under the heading, so it
    // cannot be missed by a customer who skims.
    expect(
      (await screen.findAllByText(/Settlement state is not available to us yet\./i)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("What we could not verify")).toBeTruthy();
  });

  it("shows the verified case and its reference", async () => {
    renderAt("INC-1", PENDING, ESCALATED);

    expect(await screen.findByText("Your support case")).toBeTruthy();
    expect(screen.getByText("Payments operations")).toBeTruthy();
  });

  it("marks the case step done only because a verification event exists", async () => {
    renderAt("INC-1", PENDING, ESCALATED);

    await screen.findByText("Your support case");
    expect(screen.getByText("We opened a support case")).toBeTruthy();
  });

  it("reports the recorded status next to the amount", async () => {
    renderAt("INC-1", PENDING, ESCALATED);

    await screen.findByText("Your support case");
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
  });
});

describe("an escalation whose support case could not be verified", () => {
  const FAILED: WorkflowResult = {
    ...PENDING,
    incident_id: "INC-2",
    status: "failed",
    support_case: null,
    handoff: null,
    failure: { reason: "support_case_unverified" },
  };

  it("never claims a case exists", async () => {
    renderAt("INC-2", FAILED, VERIFICATION_FAILED);

    expect(await screen.findByText(/could not confirm that this was escalated/i)).toBeTruthy();
    expect(screen.queryByText("Your support case")).toBeNull();
    expect(screen.getByText(/do not assume this has been handed to a specialist/i)).toBeTruthy();
  });

  it("still shows the recorded status as unverified", async () => {
    renderAt("INC-2", FAILED, VERIFICATION_FAILED);

    await screen.findByText(/could not confirm that this was escalated/i);
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
  });

  it("never renders the customer identifier the backend returned", async () => {
    // The API does return customer_id on the transaction. It is an identifier, not something to put
    // in front of a customer, so the screen must not surface it anywhere.
    renderAt("INC-2", FAILED, VERIFICATION_FAILED);

    await screen.findByText(/could not confirm that this was escalated/i);
    expect(document.body.textContent ?? "").not.toContain("CLI-1");
  });
});

describe("a result that is not in this session", () => {
  it("says so instead of showing anything about the movement", async () => {
    renderAt("INC-9", null, timeline("INC-9", []));

    expect(await screen.findByText(/do not have this result in this session/i)).toBeTruthy();
    expect(screen.queryByText("Your support case")).toBeNull();
    expect(screen.queryByText("Still in progress")).toBeNull();
  });
});

describe("choosing one of several candidates", () => {
  const AMBIGUOUS: WorkflowResult = {
    ...PENDING,
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
        {
          transaction_id: "TRX-A",
          transaction_status: "Approved",
          transaction_type: "Transfer",
          amount: 7541.43,
          currency: "USD",
          transaction_date: "2026-06-17T21:36:38",
        },
        {
          transaction_id: "TRX-B",
          transaction_status: "Declined",
          transaction_type: "Transfer",
          amount: 8973.13,
          currency: "USD",
          transaction_date: "2026-06-17T19:10:26",
        },
      ],
    },
  };

  /** Renders the ambiguity, then answers the follow-up POST with a failure. */
  function renderWithFailingPick() {
    const fetchImpl = ((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(null, { status: 400 }));
      }
      if (url === "/api/demo/profiles") {
        return Promise.resolve(
          new Response(JSON.stringify({ profiles: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(timeline("INC-1", ["incident_created"])), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;
    vi.stubGlobal("fetch", fetchImpl);

    render(
      <MemoryRouter initialEntries={["/resolution/INC-1"]}>
        <SessionProvider>
          <IncidentProvider>
            <Seed result={AMBIGUOUS} />
            <Routes>
              <Route path="/resolution/:incidentId" element={<ResolutionView />} />
            </Routes>
          </IncidentProvider>
        </SessionProvider>
      </MemoryRouter>,
    );
  }

  it("offers every candidate the backend returned", async () => {
    renderAt("INC-1", AMBIGUOUS, timeline("INC-1", ["incident_created"]));

    expect(await screen.findByText("Which one did you mean?")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "This one" })).toHaveLength(2);
  });

  it("tells the customer when the pick could not be checked, instead of doing nothing", async () => {
    renderWithFailingPick();

    const buttons = await screen.findAllByRole("button", { name: "This one" });
    await act(async () => {
      buttons[0].click();
    });

    expect(screen.getByText(/could not be checked/i)).toBeTruthy();
    // The customer must be told nothing was decided, not left thinking it worked.
    expect(screen.getByText(/Nothing has been decided and no action has been taken\./i)).toBeTruthy();
  });

  it("lets the customer try again after a failed pick", async () => {
    renderWithFailingPick();

    const buttons = await screen.findAllByRole("button", { name: "This one" });
    await act(async () => {
      buttons[0].click();
    });

    // The notice must not replace the list: retrying the same pick has to stay possible.
    const retry = await screen.findAllByRole("button", { name: "This one" });
    expect(retry).toHaveLength(2);
    expect((retry[0] as HTMLButtonElement).disabled).toBe(false);
  });
});
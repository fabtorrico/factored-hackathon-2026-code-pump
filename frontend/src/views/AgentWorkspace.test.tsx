import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentGate } from "../App";
import { AgentShell } from "../components/AgentShell";
import { AgentSessionProvider } from "../state/AgentSessionProvider";
import { AgentCaseView } from "./AgentCaseView";
import { AgentQueueView } from "./AgentQueueView";

/**
 * End-to-end through the agent surface: the provider opens a demo agent session, the gate waits for
 * it, and the views read persisted cases. The stub is the shape the backend actually returns.
 */

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CASE_ID = "45105b30-e998-4531-8c2a-2cfe28ff27e0";
const INCIDENT_ID = "6f7c1e2a-1111-2222-3333-444455556666";

const SESSION = {
  agent_session_id: "AGENT-1",
  display_name: "Demo specialist",
  issued_at: "2026-06-18T12:00:00Z",
  expires_at: "2026-06-18T12:30:00Z",
};

const SUMMARY = {
  case_id: CASE_ID,
  incident_id: INCIDENT_ID,
  status: "open",
  workflow_status: "escalated",
  outcome: "ESCALATE",
  reason_code: "pending_status",
  policy_rule: "G_PENDING",
  policy_version: "1.0.0",
  recommended_route: "PAYMENTS_OPERATIONS",
  created_at: "2026-06-18T12:00:00Z",
  has_handoff: true,
  movement: {
    transaction_reference: "TRX-1",
    transaction_type: "Purchase",
    transaction_status: "Pending",
    amount: "345.41",
    currency: "USD",
  },
  unresolved_count: 1,
};

const HANDOFF = {
  case_id: CASE_ID,
  incident_id: INCIDENT_ID,
  customer_request: {
    identification_mode: "exact_transaction",
    transaction_reference: "TRX-1",
    filters: null,
    in_scope: true,
    approved_with_unresolved_issue: false,
  },
  verified_facts: [
    { fact: "transaction_status", value: "Pending", source: "banking_core" },
    { fact: "transaction_amount", value: "345.41", source: "banking_core" },
  ],
  actions_taken: ["session_validated", "policy_evaluated"],
  supporting_evidence: [{ kind: "transaction_response_code", value: "51" }],
  unresolved_questions: ["final_settlement_state_unavailable"],
  policy_decision: {
    outcome: "ESCALATE",
    reason_code: "pending_status",
    policy_rule: "G_PENDING",
    policy_version: "1.0.0",
  },
  recommended_route: "PAYMENTS_OPERATIONS",
};

function event(event_type: string) {
  return {
    incident_id: INCIDENT_ID,
    occurred_at: "2026-06-18T12:00:00Z",
    event_type,
    detail: {},
  };
}

const EVENTS = [
  event("incident_created"),
  event("policy_evaluated"),
  event("support_case_verified"),
  event("workflow_escalated"),
];

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderAgent(initial: string, routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    ((url: string) => {
      if (url === "/api/agent/sessions") {
        return Promise.resolve(json(201, SESSION));
      }
      const body = routes[url];
      if (body === undefined) {
        return Promise.resolve(json(404, { error: "case_not_found", message: "Case not found." }));
      }
      return Promise.resolve(json(200, body));
    }) as typeof fetch,
  );

  render(
    <MemoryRouter initialEntries={[initial]}>
      <AgentSessionProvider>
        <Routes>
          <Route element={<AgentGate />}>
            <Route element={<AgentShell />}>
              <Route path="/agent/queue" element={<AgentQueueView />} />
              <Route path="/agent/cases/:caseId" element={<AgentCaseView />} />
            </Route>
          </Route>
        </Routes>
      </AgentSessionProvider>
    </MemoryRouter>,
  );
}

describe("the case queue", () => {
  it("lists a case that was genuinely persisted", async () => {
    renderAgent("/agent/queue", { "/api/agent/cases": { cases: [SUMMARY] } });

    expect(await screen.findByText("CASE 45105B30")).toBeTruthy();
    expect(screen.getByText("Stored")).toBeTruthy();
    expect(screen.getByText(/Purchase · USD 345.41 · Pending/)).toBeTruthy();
  });

  it("says nothing has been escalated when the queue is empty", async () => {
    renderAgent("/agent/queue", { "/api/agent/cases": { cases: [] } });

    expect(await screen.findByText("No case has been escalated yet.")).toBeTruthy();
  });
});

describe("one case in full", () => {
  it("shows the persisted handoff, its facts and the technical decision", async () => {
    renderAgent(`/agent/cases/${CASE_ID}`, {
      [`/api/agent/cases/${CASE_ID}`]: { case: SUMMARY, handoff: HANDOFF, events: EVENTS },
    });

    expect(await screen.findByText("Movement status")).toBeTruthy();
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getByText("G_PENDING")).toBeTruthy();
    expect(screen.getByText("Settlement state is not available yet.")).toBeTruthy();
    expect(screen.getByText("Policy evaluated")).toBeTruthy();
  });

  it("admits when no handoff was stored instead of inventing facts", async () => {
    renderAgent(`/agent/cases/${CASE_ID}`, {
      [`/api/agent/cases/${CASE_ID}`]: {
        case: { ...SUMMARY, has_handoff: false },
        handoff: null,
        events: EVENTS,
      },
    });

    expect(await screen.findByText("No handoff was stored for this case.")).toBeTruthy();
    expect(screen.queryByText("Verified facts")).toBeNull();
  });

  it("reports an unknown case rather than showing an empty one", async () => {
    renderAgent("/agent/cases/does-not-exist", {});

    expect(await screen.findByText("This case could not be read")).toBeTruthy();
    expect(screen.getByText("Case not found.")).toBeTruthy();
  });
});

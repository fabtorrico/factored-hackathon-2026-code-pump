import { describe, expect, it } from "vitest";

import { ApiClient, ApiError } from "./client";

/**
 * The client is the only place a session id travels, and the only place a failure becomes
 * something a view can act on. These tests pin both.
 */

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function clientReturning(response: Response | (() => Promise<Response>)) {
  const calls: { url: string; init: RequestInit | undefined }[] = [];
  const fetchImpl = ((url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return typeof response === "function" ? response() : Promise.resolve(response);
  }) as typeof fetch;
  return { client: new ApiClient(() => "SESSION-1", fetchImpl), calls };
}

describe("the session id", () => {
  it("travels in the header and nowhere else", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, { profiles: [] }));

    await client.listDemoProfiles();

    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers["X-Session-Id"]).toBe("SESSION-1");
    expect(calls[0].url).not.toContain("SESSION-1");
    expect(calls[0].init?.body ?? "").not.toContain("SESSION-1");
  });

  it("is omitted when there is no session", async () => {
    const calls: { url: string; init: RequestInit | undefined }[] = [];
    const fetchImpl = ((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(jsonResponse(200, { profiles: [] }));
    }) as typeof fetch;
    const client = new ApiClient(() => null, fetchImpl);

    await client.listDemoProfiles();

    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers["X-Session-Id"]).toBeUndefined();
  });
});

describe("failures are classified, not guessed at", () => {
  it("reads a known reason off the response", async () => {
    const { client } = clientReturning(
      jsonResponse(401, { error: "expired_session", message: "Session has expired." }),
    );

    const error = await client.getCustomerContext().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).reason).toBe("expired_session");
    expect((error as ApiError).isSessionGone).toBe(true);
  });

  it("treats an invalid session as unrecoverable too", async () => {
    const { client } = clientReturning(jsonResponse(401, { error: "invalid_session", message: "no" }));

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.isSessionGone).toBe(true);
  });

  it("does not invent a reason for an unmapped status", async () => {
    const { client } = clientReturning(new Response("<html>gateway</html>", { status: 502 }));

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.reason).toBe("tool_failure");
    expect(error.isServiceUnavailable).toBe(true);
    expect(error.message).not.toContain("gateway");
  });

  it("keeps the backend's own message when there is one", async () => {
    const { client } = clientReturning(
      jsonResponse(400, { error: "invalid_request", message: "The request contains values this banking tool does not support." }),
    );

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.message).toBe("The request contains values this banking tool does not support.");
    expect(error.isRequestRejected).toBe(true);
  });

  it("reports a transport failure as such", async () => {
    const { client } = clientReturning(() => Promise.reject(new TypeError("failed to fetch")));

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.status).toBe(0);
    expect(error.isServiceUnavailable).toBe(true);
  });

  it("does not blame the service for a request it rejected with no body", async () => {
    // The backend answers an unusable filter with a bare 400 and nothing to parse. The service is
    // plainly up, so the customer must be told to fix the details, not to wait for an outage.
    const { client } = clientReturning(new Response(null, { status: 400 }));

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.reason).toBe("invalid_request");
    expect(error.isRequestRejected).toBe(true);
    expect(error.isServiceUnavailable).toBe(false);
  });

  it("still treats an unmapped 5xx as the service being unavailable", async () => {
    const { client } = clientReturning(new Response(null, { status: 503 }));

    const error = (await client.getCustomerContext().catch((caught: unknown) => caught)) as ApiError;

    expect(error.isServiceUnavailable).toBe(true);
  });
});

describe("query building", () => {
  it("sends only the filters that have a value", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, { transactions: [] }));

    await client.getTransactions({ transaction_type: "Transfer", currency: "", channel: "Web" });

    expect(calls[0].url).toBe("/api/transactions?transaction_type=Transfer&channel=Web");
  });

  it("sends no query string at all when nothing is filtered", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, { transactions: [] }));

    await client.getTransactions();

    expect(calls[0].url).toBe("/api/transactions");
  });

  it("encodes an identifier into the path", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, {}));

    await client.getIncidentTimeline("INC/../etc");

    expect(calls[0].url).toBe("/api/incidents/INC%2F..%2Fetc/events");
  });
});

describe("incident reports", () => {
  it("posts the structured input with no extra fields", async () => {
    const { client, calls } = clientReturning(
      jsonResponse(200, { incident_id: "INC-1" }),
    );

    await client.reportIncident({ transaction_id: "TRX-1", approved_with_unresolved_issue: true });

    expect(calls[0].url).toBe("/api/incidents");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      transaction_id: "TRX-1",
      approved_with_unresolved_issue: true,
    });
  });
});
import { describe, expect, it } from "vitest";

import { AgentApiClient } from "./agent";
import { ApiError } from "./client";

/**
 * The agent client is a separate credential from the customer client. These tests pin that the
 * agent id travels only in its own header, that the surface is read-only, and that a missing case is
 * surfaced as `case_not_found` rather than a generic failure.
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
  return { client: new AgentApiClient(() => "AGENT-1", fetchImpl), calls };
}

describe("the agent session id", () => {
  it("travels in its own header and nowhere else", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, { cases: [] }));

    await client.listCases();

    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers["X-Agent-Session-Id"]).toBe("AGENT-1");
    expect(headers["X-Session-Id"]).toBeUndefined();
    expect(calls[0].url).not.toContain("AGENT-1");
  });

  it("is omitted when there is no agent session", async () => {
    const calls: { url: string; init: RequestInit | undefined }[] = [];
    const fetchImpl = ((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(jsonResponse(200, { cases: [] }));
    }) as typeof fetch;
    const client = new AgentApiClient(() => null, fetchImpl);

    await client.listCases();

    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers["X-Agent-Session-Id"]).toBeUndefined();
  });
});

describe("the agent routes", () => {
  it("mints a session with a POST", async () => {
    const { client, calls } = clientReturning(
      jsonResponse(201, { agent_session_id: "AGENT-1" }),
    );

    await client.openSession();

    expect(calls[0].url).toBe("/api/agent/sessions");
    expect(calls[0].init?.method).toBe("POST");
  });

  it("reads the queue and one case", async () => {
    const { client, calls } = clientReturning(jsonResponse(200, {}));

    await client.getCase("CASE/../etc");

    expect(calls[0].url).toBe("/api/agent/cases/CASE%2F..%2Fetc");
    expect(calls[0].init?.method).toBeUndefined();
  });
});

describe("agent failures", () => {
  it("reads case_not_found off the response", async () => {
    const { client } = clientReturning(
      jsonResponse(404, { error: "case_not_found", message: "Case not found." }),
    );

    const error = (await client.getCase("nope").catch((caught: unknown) => caught)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.reason).toBe("case_not_found");
  });

  it("reports a transport failure without blaming the case", async () => {
    const { client } = clientReturning(() => Promise.reject(new TypeError("failed to fetch")));

    const error = (await client.listCases().catch((caught: unknown) => caught)) as ApiError;

    expect(error.status).toBe(0);
    expect(error.isServiceUnavailable).toBe(true);
  });
});

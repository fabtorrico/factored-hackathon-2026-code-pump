import { ApiError, TRANSPORT, toApiError } from "./client";
import type { AgentCaseDetail, AgentCaseList, AgentSession } from "./types";

/**
 * The read-only agent workspace client.
 *
 * It is deliberately separate from the customer client: it carries a different credential header
 * (`X-Agent-Session-Id`), it can only read cases, and there is no method here that changes
 * anything. Sharing the error classification keeps the two surfaces consistent without letting an
 * agent credential ever travel as a customer one.
 */
export class AgentApiClient {
  constructor(
    private readonly agentSessionId: () => string | null,
    private readonly fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const agentSessionId = this.agentSessionId();
    let response: Response;
    try {
      response = await this.fetchImpl(path, {
        ...init,
        headers: {
          Accept: "application/json",
          ...(agentSessionId ? { "X-Agent-Session-Id": agentSessionId } : {}),
          ...init?.headers,
        },
      });
    } catch {
      throw new ApiError(TRANSPORT, "The agent workspace could not be reached.", 0);
    }

    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as T;
  }

  openSession(): Promise<AgentSession> {
    return this.request("/api/agent/sessions", { method: "POST" });
  }

  listCases(): Promise<AgentCaseList> {
    return this.request("/api/agent/cases");
  }

  getCase(caseId: string): Promise<AgentCaseDetail> {
    return this.request(`/api/agent/cases/${encodeURIComponent(caseId)}`);
  }
}

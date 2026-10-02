import type {
  CustomerContext,
  CustomerTransactions,
  DemoProfile,
  DemoSession,
  IncidentTimeline,
  Reason,
  Transaction,
  WorkflowResult,
} from "./types";

/**
 * One error type for every failed request, so a view can tell "your session expired" apart from
 * "the service is down" without inspecting HTTP status codes or parsing messages.
 */
export class ApiError extends Error {
  readonly reason: Reason;
  readonly status: number;

  constructor(reason: Reason, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.reason = reason;
    this.status = status;
  }

  /** The session is gone or was never valid: the caller has to start over. */
  get isSessionGone(): boolean {
    return this.reason === "invalid_session" || this.reason === "expired_session";
  }

  /** The service could not be reached or could not read the curated data. */
  get isServiceUnavailable(): boolean {
    return this.reason === "data_unavailable" || this.reason === "tool_failure" || this.status === 0;
  }

  /** The request itself was rejected, so retrying it unchanged cannot help. */
  get isRequestRejected(): boolean {
    return this.reason === "invalid_request" || this.status === 422;
  }
}

/** A transport failure, before the service could say anything about why. */
export const TRANSPORT: Reason = "tool_failure";

function toReason(value: unknown): Reason | null {
  if (typeof value !== "string") {
    return null;
  }
  const known: Reason[] = [
    "invalid_session",
    "expired_session",
    "unauthorized_resource",
    "customer_not_found",
    "transaction_not_found",
    "incident_not_found",
    "case_not_found",
    "invalid_request",
    "data_unavailable",
    "tool_failure",
  ];
  return known.includes(value as Reason) ? (value as Reason) : null;
}

export class ApiClient {
  constructor(
    private readonly sessionId: () => string | null,
    private readonly fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const sessionId = this.sessionId();
    let response: Response;
    try {
      response = await this.fetchImpl(path, {
        ...init,
        headers: {
          Accept: "application/json",
          // The session travels in the header the Banking Core authenticates against, never in a
          // path or a body, so an identifier can never be mistaken for proof of identity.
          ...(sessionId ? { "X-Session-Id": sessionId } : {}),
          ...init?.headers,
        },
      });
    } catch {
      throw new ApiError(TRANSPORT, "The banking service could not be reached.", 0);
    }

    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as T;
  }

  listDemoProfiles(): Promise<{ profiles: DemoProfile[] }> {
    return this.request("/api/demo/profiles");
  }

  openDemoSession(profileId: string): Promise<DemoSession> {
    return this.request("/api/demo/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId }),
    });
  }

  getCustomerContext(): Promise<CustomerContext> {
    return this.request("/api/customer/context");
  }

  getTransactions(filters: Record<string, string> = {}): Promise<CustomerTransactions> {
    return this.request(`/api/transactions${query(filters)}`);
  }

  getTransaction(transactionId: string): Promise<Transaction> {
    return this.request(`/api/transactions/${encodeURIComponent(transactionId)}`);
  }

  reportIncident(payload: Record<string, unknown>): Promise<WorkflowResult> {
    return this.request("/api/incidents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  getIncidentTimeline(incidentId: string): Promise<IncidentTimeline> {
    return this.request(`/api/incidents/${encodeURIComponent(incidentId)}/events`);
  }
}

export async function toApiError(response: Response): Promise<ApiError> {
  let reason: Reason | null = null;
  let message = "The request could not be completed.";
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object") {
      const candidate = body as { error?: unknown; message?: unknown };
      reason = toReason(candidate.error);
      if (typeof candidate.message === "string" && candidate.message.length > 0) {
        message = candidate.message;
      }
    }
  } catch {
    // A non-JSON error body is not an excuse to invent a reason.
  }

  if (reason === null) {
    // The service answered, so blaming it for being unavailable would be wrong. An unmapped 4xx is
    // a request it refused; only an unreachable or failing service is a transport failure.
    reason =
      response.status === 0 || response.status >= 500
        ? TRANSPORT
        : ("invalid_request" satisfies Reason);
    message =
      response.status === 0 || response.status >= 500
        ? "The banking service could not be reached."
        : "Those details were not accepted. Check them and try again.";
  }

  // An unmapped status must not masquerade as a known reason.
  return new ApiError(reason, message, response.status);
}

function query(filters: Record<string, string>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== "") {
      search.set(key, value);
    }
  }
  const encoded = search.toString();
  return encoded === "" ? "" : `?${encoded}`;
}
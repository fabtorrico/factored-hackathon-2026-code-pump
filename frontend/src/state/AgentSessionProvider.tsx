import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { AgentApiClient } from "../api/agent";
import type { AgentSession } from "../api/types";

type AgentStatus = "loading" | "ready" | "error";

interface AgentSessionState {
  api: AgentApiClient;
  /** Null until the demo agent session has been opened. The id never leaves this module. */
  session: AgentSession | null;
  status: AgentStatus;
  error: string | null;
  /** Try again after the workspace could not be opened. */
  retry: () => void;
  /** Start over after the session has expired mid-read. */
  reopen: () => void;
}

const AgentSessionContext = createContext<AgentSessionState | null>(null);

/**
 * Owns the demo-only agent credential.
 *
 * This is intentionally not the customer session provider. An agent session is a separate opaque id
 * sent as `X-Agent-Session-Id`; the customer session id is never reused here, and nothing on this
 * surface can write.
 */
export function AgentSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AgentSession | null>(null);
  const [status, setStatus] = useState<AgentStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  // The credential is read through a ref so the client stays stable across renders.
  const sessionRef = useRef<AgentSession | null>(null);
  const api = useMemo(
    () => new AgentApiClient(() => sessionRef.current?.agent_session_id ?? null),
    [],
  );

  const adopt = useCallback((next: AgentSession | null) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const open = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      adopt(await api.openSession());
      setStatus("ready");
    } catch (caught) {
      adopt(null);
      setError(caught instanceof Error ? caught.message : "The agent workspace could not be opened.");
      setStatus("error");
    }
  }, [api, adopt]);

  // A session is opened once on mount. `api` and `open` are stable, so this stays mount-only.
  useEffect(() => {
    void open().catch(() => undefined);
  }, [open]);

  const reopen = useCallback(() => {
    adopt(null);
    void open().catch(() => undefined);
  }, [adopt, open]);

  const value = useMemo<AgentSessionState>(
    () => ({ api, session, status, error, retry: () => void open(), reopen }),
    [api, session, status, error, open, reopen],
  );

  return <AgentSessionContext.Provider value={value}>{children}</AgentSessionContext.Provider>;
}

export function useAgentSession(): AgentSessionState {
  const value = useContext(AgentSessionContext);
  if (value === null) {
    throw new Error("useAgentSession must be used inside an AgentSessionProvider");
  }
  return value;
}

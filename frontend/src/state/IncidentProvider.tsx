import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { WorkflowResult } from "../api/types";

/**
 * Holds the results of the incidents raised in this browser session.
 *
 * Results stay in memory only: they are never written to storage, because a stored incident result
 * would outlive the session that authenticated it. Re-opening the resolution page in a new session
 * honestly reports that the result is not available rather than showing a stale answer.
 */
interface IncidentState {
  results: Readonly<Record<string, WorkflowResult>>;
  record: (result: WorkflowResult) => void;
  get: (incidentId: string) => WorkflowResult | undefined;
}

const IncidentContext = createContext<IncidentState | null>(null);

export function IncidentProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<Record<string, WorkflowResult>>({});

  const record = useCallback((result: WorkflowResult) => {
    setResults((current) => ({ ...current, [result.incident_id]: result }));
  }, []);

  const get = useCallback((incidentId: string) => results[incidentId], [results]);

  const value = useMemo<IncidentState>(() => ({ results, record, get }), [results, record, get]);

  return <IncidentContext.Provider value={value}>{children}</IncidentContext.Provider>;
}

export function useIncidents(): IncidentState {
  const value = useContext(IncidentContext);
  if (value === null) {
    throw new Error("useIncidents must be used inside an IncidentProvider");
  }
  return value;
}
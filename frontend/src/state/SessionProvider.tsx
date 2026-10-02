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

import { ApiClient } from "../api/client";
import type { DemoProfile, DemoSession } from "../api/types";

interface SessionState {
  api: ApiClient;
  /** Null until a demo profile has been chosen. The session id never leaves this module. */
  session: DemoSession | null;
  profiles: DemoProfile[];
  loadingProfiles: boolean;
  starting: string | null;
  error: string | null;
  chooseProfile: (profileId: string) => Promise<void>;
  endSession: () => void;
  dismissError: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  // The session id lives here and only here. It is sent as a header and never rendered, logged or
  // stored, so nothing downstream can leak the bearer credential.
  const [session, setSession] = useState<DemoSession | null>(null);
  const [profiles, setProfiles] = useState<DemoProfile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The client reads the credential through a ref rather than through state, so opening or closing a
  // session never replaces the client. A stable client keeps the profile effect below genuinely
  // mount-only, and stops every consumer from re-rendering each time a session starts.
  const sessionRef = useRef<DemoSession | null>(null);
  const api = useMemo(() => new ApiClient(() => sessionRef.current?.session_id ?? null), []);

  const adoptSession = useCallback((next: DemoSession | null) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const loadProfiles = useCallback(async () => {
    setLoadingProfiles(true);
    try {
      const catalogue = await api.listDemoProfiles();
      setProfiles(catalogue.profiles);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The demo profiles could not be loaded.");
    } finally {
      setLoadingProfiles(false);
    }
  }, [api]);

  // The catalogue is unauthenticated and static for a given curated database, so it is fetched once
  // on mount. `api` is stable, so opening a session cannot trigger a second fetch.
  useEffect(() => {
    void loadProfiles().catch(() => undefined);
  }, [loadProfiles]);

  const chooseProfile = useCallback(
    async (profileId: string) => {
      setStarting(profileId);
      setError(null);
      try {
        adoptSession(await api.openDemoSession(profileId));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "The session could not be opened.");
      } finally {
        setStarting(null);
      }
    },
    [api, adoptSession],
  );

  const endSession = useCallback(() => {
    adoptSession(null);
    setError(null);
  }, [adoptSession]);

  const dismissError = useCallback(() => setError(null), []);

  const value = useMemo<SessionState>(
    () => ({
      api,
      session,
      profiles,
      loadingProfiles,
      starting,
      error,
      chooseProfile,
      endSession,
      dismissError,
    }),
    [api, session, profiles, loadingProfiles, starting, error, chooseProfile, endSession, dismissError],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (value === null) {
    throw new Error("useSession must be used inside a SessionProvider");
  }
  return value;
}
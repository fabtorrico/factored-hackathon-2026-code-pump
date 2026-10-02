import { BrowserRouter, Link, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AgentShell } from "./components/AgentShell";
import { AppShell } from "./components/AppShell";
import { ErrorNotice, Loading } from "./components/primitives";
import { AgentSessionProvider, useAgentSession } from "./state/AgentSessionProvider";
import { IncidentProvider } from "./state/IncidentProvider";
import { SessionProvider, useSession } from "./state/SessionProvider";
import { AgentCaseView } from "./views/AgentCaseView";
import { AgentQueueView } from "./views/AgentQueueView";
import { MovementDetailView } from "./views/MovementDetailView";
import { MovementsView } from "./views/MovementsView";
import { OverviewView } from "./views/OverviewView";
import { ReportIssueView } from "./views/ReportIssueView";
import { ResolutionView } from "./views/ResolutionView";
import { WelcomeView } from "./views/WelcomeView";

/**
 * Routes behind a session. Without one there is nothing to read, so these paths redirect to the
 * profile chooser instead of mounting a view that would immediately fail.
 */
function RequireSession() {
  const { session } = useSession();
  if (session === null) {
    return <Navigate to="/welcome" replace />;
  }
  return <Outlet />;
}

/**
 * The customer surface's providers.
 *
 * Scoped to the customer routes so the agent workspace never mounts a customer session provider and
 * the two credentials cannot cross.
 */
function CustomerProviders() {
  return (
    <SessionProvider>
      <IncidentProvider>
        <Outlet />
      </IncidentProvider>
    </SessionProvider>
  );
}

/**
 * The agent surface's providers and its own gate.
 *
 * The gate waits for the demo agent session before rendering any case view, so a read never races
 * the credential, and a workspace that cannot be opened says so rather than showing empty data.
 */
export function AgentGate() {
  const { session, status, error, retry } = useAgentSession();

  if (status === "loading") {
    return (
      <main className="page page--welcome">
        <Loading label="Opening the agent workspace" />
      </main>
    );
  }

  if (session === null) {
    return (
      <main className="page page--welcome">
        <ErrorNotice title="The agent workspace could not be opened" onRetry={retry}>
          <p>{error ?? "The demo agent session could not be started."}</p>
        </ErrorNotice>
        <div className="button-row">
          <Link className="button button--quiet" to="/">
            Back to the customer site
          </Link>
        </div>
      </main>
    );
  }

  return <Outlet />;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<CustomerProviders />}>
          <Route path="/welcome" element={<WelcomeView />} />
          <Route element={<RequireSession />}>
            <Route element={<AppShell />}>
              <Route path="/" element={<OverviewView />} />
              <Route path="/movements" element={<MovementsView />} />
              <Route path="/movements/:transactionId" element={<MovementDetailView />} />
              <Route path="/report" element={<ReportIssueView />} />
              <Route path="/report/:transactionId" element={<ReportIssueView />} />
              <Route path="/resolution/:incidentId" element={<ResolutionView />} />
            </Route>
          </Route>
        </Route>

        <Route
          path="/agent"
          element={
            <AgentSessionProvider>
              <Outlet />
            </AgentSessionProvider>
          }
        >
          <Route element={<AgentGate />}>
            <Route element={<AgentShell />}>
              <Route index element={<Navigate to="queue" replace />} />
              <Route path="queue" element={<AgentQueueView />} />
              <Route path="cases/:caseId" element={<AgentCaseView />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

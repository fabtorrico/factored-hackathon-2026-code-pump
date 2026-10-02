import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { IncidentProvider } from "./state/IncidentProvider";
import { SessionProvider, useSession } from "./state/SessionProvider";
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

export function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <IncidentProvider>
          <Routes>
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
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </IncidentProvider>
      </SessionProvider>
    </BrowserRouter>
  );
}
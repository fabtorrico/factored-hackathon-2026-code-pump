import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useSession } from "../state/SessionProvider";

/**
 * The shell a signed-in customer sees.
 *
 * The display name comes from the chosen demo profile. The session id is never rendered, and the
 * curated customer identifier behind the profile is never sent to the browser at all.
 */
export function AppShell() {
  const { session, endSession } = useSession();
  const navigate = useNavigate();

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="shell__header">
        <div className="shell__brand">
          <span className="shell__mark" aria-hidden="true" />
          <span>Code Pump</span>
        </div>
        <nav aria-label="Primary" className="shell__nav">
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/movements">Movements</NavLink>
          <NavLink to="/report">Report an issue</NavLink>
        </nav>
        <div className="shell__account">
          <span className="shell__name">{session?.display_name ?? "Demo customer"}</span>
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              endSession();
              navigate("/", { replace: true });
            }}
          >
            Switch customer
          </button>
        </div>
      </header>
      <div id="main" className="shell__main">
        <Outlet />
      </div>
    </div>
  );
}
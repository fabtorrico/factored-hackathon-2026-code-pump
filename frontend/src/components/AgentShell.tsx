import { Link, NavLink, Outlet } from "react-router-dom";

import { useAgentSession } from "../state/AgentSessionProvider";

/**
 * The shell a support specialist sees.
 *
 * It is deliberately not the customer shell and it carries no customer session. The only read
 * surface is the persisted case queue; there is no link to refunds, reversals or any write action,
 * because none exists on this surface.
 */
export function AgentShell() {
  const { session } = useAgentSession();

  return (
    <div className="shell shell--agent">
      <a className="skip-link" href="#agent-main">
        Skip to content
      </a>
      <header className="shell__header">
        <div className="shell__brand">
          <span className="shell__mark shell__mark--agent" aria-hidden="true" />
          <span>Code Pump · Agent</span>
        </div>
        <nav aria-label="Agent" className="shell__nav">
          <NavLink to="/agent/queue">Queue</NavLink>
        </nav>
        <div className="shell__account">
          <span className="shell__name">{session?.display_name ?? "Demo specialist"}</span>
          <Link className="button button--quiet" to="/">
            Customer site
          </Link>
        </div>
      </header>
      <div id="agent-main" className="shell__main">
        <Outlet />
      </div>
    </div>
  );
}

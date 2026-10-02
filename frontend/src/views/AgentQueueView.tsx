import { useCallback } from "react";
import { Link } from "react-router-dom";

import type { AgentCaseSummary } from "../api/types";
import {
  Card,
  EmptyState,
  ErrorNotice,
  Loading,
  OutcomePill,
  StatusPill,
} from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { caseReference, movementAmount, outcomeTone } from "../lib/agent";
import { formatDateTime, humanize, shortReference } from "../lib/format";
import { useAgentSession } from "../state/AgentSessionProvider";

/**
 * The case queue.
 *
 * Every row is a support case that actually exists in the operational store. There is no fixture
 * here: if the queue is empty, nothing has been escalated. The queue never shows a customer
 * identity, because the workspace never receives one.
 */
export function AgentQueueView() {
  const { api, reopen } = useAgentSession();

  const load = useCallback((client: typeof api) => client.listCases(), [api]);
  const { data, error, loading, reload } = useResource(api, load, reopen);
  const cases = data?.cases ?? [];

  return (
    <main className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Agent workspace</p>
          <h1 className="page__title">Support case queue</h1>
        </div>
        <p className="muted page__note">
          Read-only. Each case is what the workflow escalated, with the handoff it stored.
        </p>
      </header>

      {error !== null && (
        <ErrorNotice title="The queue could not be read" onRetry={reload}>
          <p>{error}</p>
        </ErrorNotice>
      )}

      <Card title={cases.length === 1 ? "1 case" : `${cases.length} cases`}>
        {loading ? (
          <Loading label="Loading the case queue" />
        ) : cases.length === 0 ? (
          <EmptyState title="No case has been escalated yet.">
            <p className="muted">
              A case appears here only after the workflow opens one and reads it back. Nothing has
              been escalated from this workspace's data.
            </p>
          </EmptyState>
        ) : (
          <ul className="queue">
            {cases.map((entry) => (
              <li key={entry.case_id} className="queue__item">
                <AgentQueueRow entry={entry} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </main>
  );
}

function AgentQueueRow({ entry }: { entry: AgentCaseSummary }) {
  return (
    <Link className="queue__link" to={`/agent/cases/${entry.case_id}`}>
      <div className="queue__head">
        <span className="queue__ref">{caseReference(entry.case_id)}</span>
        {entry.workflow_status !== null && <StatusPill status={entry.workflow_status} />}
        {entry.outcome !== null && (
          <OutcomePill label={humanize(entry.outcome)} tone={outcomeTone(entry.outcome)} />
        )}
      </div>
      <p className="queue__movement">
        {humanize(entry.movement.transaction_type)} · {movementAmount(entry.movement)} ·{" "}
        {humanize(entry.movement.transaction_status)}
      </p>
      <dl className="queue__meta">
        <div>
          <dt>Incident</dt>
          <dd>{shortReference(entry.incident_id)}</dd>
        </div>
        <div>
          <dt>Opened</dt>
          <dd>{formatDateTime(entry.created_at)}</dd>
        </div>
        <div>
          <dt>Route</dt>
          <dd>{humanize(entry.recommended_route)}</dd>
        </div>
        <div>
          <dt>Handoff</dt>
          <dd>{entry.has_handoff ? "Stored" : "Not stored"}</dd>
        </div>
        <div>
          <dt>Unresolved</dt>
          <dd>{entry.unresolved_count}</dd>
        </div>
      </dl>
    </Link>
  );
}

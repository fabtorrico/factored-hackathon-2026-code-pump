import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import type { AgentCaseDetail, Handoff } from "../api/types";
import {
  Card,
  ErrorNotice,
  Loading,
  OutcomePill,
  StatusPill,
} from "../components/primitives";
import { useResource } from "../hooks/useResource";
import {
  caseReference,
  describeAction,
  describeEvidence,
  describeFact,
  describeFactSource,
  describeFactValue,
  describePolicyDecision,
  describePolicyReason,
  describePolicyRule,
  describeUnresolved,
  movementAmount,
  outcomeTone,
} from "../lib/agent";
import { formatDateTime, humanize, NOT_RECORDED } from "../lib/format";
import { incidentReference } from "../lib/reference";
import { describeEvent } from "../lib/steps";
import { useAgentSession } from "../state/AgentSessionProvider";

/**
 * One case, in full.
 *
 * The specialist sees the exact handoff that was persisted at escalation, the recorded timeline and
 * the technical policy metadata. When no handoff was stored, the screen says so instead of
 * reconstructing one, and the movement reference falls back to the incident's own record.
 */
export function AgentCaseView() {
  const { caseId = "" } = useParams();
  const { api, reopen } = useAgentSession();

  const load = useCallback((client: typeof api) => client.getCase(caseId), [api, caseId]);
  const { data, error, loading, reload } = useResource(api, load, reopen);

  return (
    <main className="page">
      <nav aria-label="Breadcrumb" className="breadcrumb">
        <Link to="/agent/queue">← Back to the queue</Link>
      </nav>

      {loading ? (
        <Loading label="Loading the case" />
      ) : error !== null ? (
        <ErrorNotice title="This case could not be read" onRetry={reload}>
          <p>{error}</p>
          <p className="muted">
            If the case was never escalated, it will not be here. Return to the queue to see the
            cases that exist.
          </p>
        </ErrorNotice>
      ) : data === null ? null : (
        <AgentCaseBody detail={data} />
      )}
    </main>
  );
}

function AgentCaseBody({ detail }: { detail: AgentCaseDetail }) {
  const { case: entry, handoff, events } = detail;

  return (
    <>
      <header className="page__header">
        <div>
          <p className="eyebrow">Case</p>
          <h1 className="page__title">{caseReference(entry.case_id)}</h1>
          <p className="muted">
            <span className="code">{entry.case_id}</span>
          </p>
        </div>
        <div className="page__pills">
          <StatusPill status={entry.workflow_status ?? "unknown"} />
          {entry.outcome !== null && (
            <OutcomePill label={humanize(entry.outcome)} tone={outcomeTone(entry.outcome)} />
          )}
        </div>
      </header>

      <Card title="At a glance">
        <dl className="fields fields--wide">
          <div className="field">
            <dt className="field__label">Incident</dt>
            <dd className="field__value">
              <span className="code">{incidentReference(entry.incident_id)}</span>
            </dd>
          </div>
          <div className="field">
            <dt className="field__label">Opened</dt>
            <dd className="field__value">{formatDateTime(entry.created_at)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Route</dt>
            <dd className="field__value">{humanize(entry.recommended_route)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Handoff</dt>
            <dd className="field__value">{entry.has_handoff ? "Stored" : "Not stored"}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Unresolved</dt>
            <dd className="field__value">{entry.unresolved_count}</dd>
          </div>
        </dl>
      </Card>

      <Card title="Movement on record">
        <dl className="fields fields--wide">
          <div className="field">
            <dt className="field__label">Reference</dt>
            <dd className="field__value">
              {entry.movement.transaction_reference === null ? (
                <span className="muted">{NOT_RECORDED}</span>
              ) : (
                <span className="code">{entry.movement.transaction_reference}</span>
              )}
            </dd>
          </div>
          <div className="field">
            <dt className="field__label">Type</dt>
            <dd className="field__value">{humanize(entry.movement.transaction_type)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Status</dt>
            <dd className="field__value">{humanize(entry.movement.transaction_status)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Amount</dt>
            <dd className="field__value">{movementAmount(entry.movement)}</dd>
          </div>
        </dl>
      </Card>

      {handoff === null ? (
        <Card title="Handoff">
          <div className="notice notice--attention">
            <p className="notice__title">No handoff was stored for this case.</p>
            <p className="muted">
              This case exists in the operational store, but the structured handoff is not there. Do
              not treat the facts above as verified by the workflow; they come from the incident
              record alone.
            </p>
          </div>
        </Card>
      ) : (
        <HandoffSections handoff={handoff} />
      )}

      <Card title="Workflow timeline">
        {events.length === 0 ? (
          <p className="muted">No workflow events are on record for this incident.</p>
        ) : (
          <ol className="timeline">
            {events.map((event, index) => (
              <li key={`${event.occurred_at}-${index}`} className="timeline__item">
                <span className="timeline__dot" aria-hidden="true" />
                <div className="timeline__body">
                  <p className="timeline__label">{describeEvent(event)}</p>
                  <p className="timeline__time">{formatDateTime(event.occurred_at)}</p>
                  <details className="timeline__code">
                    <summary>Event code</summary>
                    <code className="code">{event.event_type}</code>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}

function HandoffSections({ handoff }: { handoff: Handoff }) {
  const { customer_request: request, policy_decision: decision } = handoff;

  return (
    <>
      <Card title="Customer request">
        <dl className="fields fields--wide">
          <div className="field">
            <dt className="field__label">Identified by</dt>
            <dd className="field__value">{humanize(request.identification_mode)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Movement reference</dt>
            <dd className="field__value">
              {request.transaction_reference === null ? (
                <span className="muted">{NOT_RECORDED}</span>
              ) : (
                <span className="code">{request.transaction_reference}</span>
              )}
            </dd>
          </div>
          <div className="field">
            <dt className="field__label">In scope</dt>
            <dd className="field__value">{request.in_scope ? "Yes" : "No"}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Approved issue open</dt>
            <dd className="field__value">{request.approved_with_unresolved_issue ? "Yes" : "No"}</dd>
          </div>
          {request.filters !== null && (
            <div className="field">
              <dt className="field__label">Filters</dt>
              <dd className="field__value">
                {Object.entries(request.filters).map(([key, value]) => (
                  <span key={key} className="chip">
                    {humanize(key)}: {value === null ? NOT_RECORDED : String(value)}
                  </span>
                ))}
              </dd>
            </div>
          )}
        </dl>
      </Card>

      <Card title="Verified facts">
        {handoff.verified_facts.length === 0 ? (
          <p className="muted">No facts were recorded.</p>
        ) : (
          <ul className="facts">
            {handoff.verified_facts.map((fact) => (
              <li key={fact.fact} className="fact">
                <span className="fact__name">{describeFact(fact)}</span>
                <span className="fact__value">{describeFactValue(fact)}</span>
                <span className="fact__source">{describeFactSource(fact.source)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Supporting evidence">
        {handoff.supporting_evidence.length === 0 ? (
          <p className="muted">No supporting evidence was recorded.</p>
        ) : (
          <dl className="fields fields--wide">
            {handoff.supporting_evidence.map((item) => (
              <div className="field" key={`${item.kind}-${item.value}`}>
                <dt className="field__label">{describeEvidence(item.kind)}</dt>
                <dd className="field__value">
                  <span className="code">{item.value}</span>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </Card>

      <Card title="Actions taken">
        {handoff.actions_taken.length === 0 ? (
          <p className="muted">No action was recorded.</p>
        ) : (
          <>
            <p className="muted">
              The workflow records an action only after it has written it and read it back. A write
              that could not be confirmed is not listed as taken.
            </p>
            <ol className="actions">
              {handoff.actions_taken.map((action, index) => (
                <li key={action} className="actions__item">
                  <span className="actions__step" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span>{describeAction(action)}</span>
                </li>
              ))}
            </ol>
          </>
        )}
      </Card>

      <Card title="Unresolved questions">
        {handoff.unresolved_questions.length === 0 ? (
          <p className="muted">Nothing is marked unresolved on this handoff.</p>
        ) : (
          <ul className="bullets">
            {handoff.unresolved_questions.map((code) => (
              <li key={code}>{describeUnresolved(code)}</li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Policy decision">
        <dl className="fields fields--wide">
          <div className="field">
            <dt className="field__label">Outcome</dt>
            <dd className="field__value">{humanize(decision.outcome)}</dd>
          </div>
          <div className="field">
            <dt className="field__label">Rule</dt>
            <dd className="field__value">
              {describePolicyRule(decision.policy_rule)}{" "}
              <span className="code">{decision.policy_rule}</span>
            </dd>
          </div>
          <div className="field">
            <dt className="field__label">Reason</dt>
            <dd className="field__value">
              {describePolicyReason(decision.reason_code)}{" "}
              <span className="code">{decision.reason_code}</span>
            </dd>
          </div>
          <div className="field">
            <dt className="field__label">Version</dt>
            <dd className="field__value">
              <span className="code">{decision.policy_version}</span>
            </dd>
          </div>
        </dl>
        <p className="muted footnote">{describePolicyDecision(decision)}</p>
        <p className="muted footnote">
          This is a synthetic prototype policy. It is not a real bank, settlement or regulatory
          policy.
        </p>
      </Card>
    </>
  );
}

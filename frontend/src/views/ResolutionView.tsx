import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import type { WorkflowResult } from "../api/types";
import { Card, EmptyState, ErrorNotice, Loading, OutcomePill, StatusPill } from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { formatAmount, formatDateTime, humanize, NOT_RECORDED } from "../lib/format";
import { caseReference, incidentReference } from "../lib/reference";
import { presentOutcome } from "../lib/outcome";
import { buildSteps, markCaseStep } from "../lib/steps";
import { useIncidents } from "../state/IncidentProvider";
import { useSession } from "../state/SessionProvider";

/**
 * Incident Resolution Center.
 *
 * Shows what happened to one request: the steps the workflow actually recorded, the outcome the
 * policy returned, and — when it escalated — the reference and exactly what is still unverified.
 *
 * Every claim on this screen traces to a field the backend returned. Nothing is derived, and a
 * verification failure is shown as a failure.
 */
export function ResolutionView() {
  const { incidentId = "" } = useParams();
  const { api, endSession } = useSession();
  const { get, record } = useIncidents();
  const navigate = useNavigate();

  const result = get(incidentId);

  // Picking a candidate re-runs the workflow on exactly that movement. The customer stays here
  // until it succeeds, so a failure has to be shown rather than swallowed.
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const chooseCandidate = useCallback(
    async (transactionId: string) => {
      setChecking(true);
      setFollowUpError(null);
      const failure = await submitFollowUp(api, record, endSession, navigate, transactionId);
      setFollowUpError(failure);
      setChecking(false);
    },
    [api, record, endSession, navigate],
  );

  // The timeline is read from the backend rather than reconstructed here, so the steps on screen are
  // the recorded ones. An incident the backend will not attribute to this session has no timeline,
  // and that is reported rather than papered over.
  const load = useCallback(
    (client: typeof api) => client.getIncidentTimeline(incidentId),
    [api, incidentId],
  );
  const { data, error, loading } = useResource(api, load, endSession);

  const timeline = data?.events ?? [];
  const steps = result === undefined ? [] : markCaseStep(buildSteps(timeline, result), timeline);

  return (
    <main className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Incident</p>
          <h1 className="page__title">
            {result === undefined ? "This request" : "What happened"}
          </h1>
          <p className="muted">
            Reference <span className="code">{incidentReference(incidentId)}</span>
          </p>
        </div>
        {result !== undefined && <OutcomePill {...presentOutcome(result)} />}
      </header>

      {result === undefined ? (
        <EmptyState title="We do not have this result in this session.">
          <p className="muted">
            Results are kept in memory for the session that raised them, so opening this reference
            later or in another session cannot show it. Nothing is lost from your account — raise the
            issue again and we will check the same movement.
          </p>
          <div className="button-row">
            <Link className="button button--primary" to="/movements">
              Go to my movements
            </Link>
            <Link className="button button--quiet" to="/report">
              Report an issue
            </Link>
          </div>
        </EmptyState>
      ) : (
        <ResolutionBody
          result={result}
          steps={steps}

          loadingTimeline={loading}
          timelineError={error}
          followUpError={followUpError}
          checking={checking}
          onChoose={(transactionId) => {
            void chooseCandidate(transactionId);
          }}
        />
      )}
    </main>
  );
}

/**
 * Re-checks exactly the movement the customer picked. Returns a message to show when it could not be
 * done, so a failed pick is never a button that silently does nothing.
 */
async function submitFollowUp(
  api: { reportIncident: (payload: Record<string, unknown>) => Promise<WorkflowResult> },
  record: (result: WorkflowResult) => void,
  endSession: () => void,
  navigate: (to: string, options?: { replace?: boolean }) => void,
  transactionId: string,
): Promise<string | null> {
  try {
    const next = await api.reportIncident({ transaction_id: transactionId });
    record(next);
    navigate(`/resolution/${next.incident_id}`, { replace: true });
    return null;
  } catch (caught) {
    if (caught instanceof ApiError && caught.isSessionGone) {
      endSession();
      return null;
    }
    return caught instanceof Error
      ? caught.message
      : "That movement could not be checked. Please try again.";
  }
}

function ResolutionBody({
  result,
  steps,
  loadingTimeline,
  timelineError,
  followUpError,
  checking,
  onChoose,
}: {
  result: WorkflowResult;
  steps: ReturnType<typeof buildSteps>;
  loadingTimeline: boolean;
  timelineError: string | null;
  followUpError: string | null;
  checking: boolean;
  onChoose: (transactionId: string) => void;
}) {
  const shown = presentOutcome(result);

  return (
    <>
      <Card>
        <p className="outcome__headline">{shown.headline}</p>
        {shown.paragraphs.map((paragraph) => (
          <p key={paragraph} className="muted">
            {paragraph}
          </p>
        ))}
        {shown.caveats.length > 0 && (
          <div className="notice notice--attention">
            <p className="notice__title">What we could not verify</p>
            <ul className="bullets">
              {shown.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {result.clarification !== null && result.clarification.candidates.length > 0 && (
        <Card title="Which one did you mean?">
          <p className="muted">
            Nothing has been decided yet. Pick the movement you meant and we will check exactly that
            one.
          </p>
          <ul className="candidates">
            {result.clarification.candidates.map((candidate) => (
              <li key={candidate.transaction_id}>
                <div className="candidate">
                  <div>
                    <p className="candidate__type">{humanize(candidate.transaction_type)}</p>
                    <p className="candidate__meta">
                      {formatAmount(candidate.amount, candidate.currency)} ·{" "}
                      {formatDateTime(candidate.transaction_date)}
                    </p>
                  </div>
                  <div className="candidate__side">
                    <span className="chip">{humanize(candidate.transaction_status)}</span>
                    <button
                      type="button"
                      className="button button--primary"
                      disabled={checking}
                      onClick={() => onChoose(candidate.transaction_id)}
                    >
                      {checking ? "Checking…" : "This one"}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {checking && <p className="muted">Checking that one movement now.</p>}
          {followUpError !== null && (
            <ErrorNotice title="That movement could not be checked">
              <p>{followUpError}</p>
              <p className="muted">Nothing has been decided and no action has been taken.</p>
            </ErrorNotice>
          )}
        </Card>
      )}

      {result.clarification !== null && result.clarification.candidates.length === 0 && (
        <Card title="No matching movement">
          <p className="muted">
            Nothing on your record matches that description, so nothing has been decided. Try a
            broader search.
          </p>
          <Link className="button button--primary" to="/report">
            Search again
          </Link>
        </Card>
      )}

      <Card title="The movement we checked">
        {result.verified_transaction === null ? (
          <p className="muted">
            No single movement was identified, so no facts about one are shown here.
          </p>
        ) : (
          <>
            <dl className="fields fields--wide">
              <div className="field">
                <dt className="field__label">Status</dt>
                <dd className="field__value">
                  <StatusPill status={result.verified_transaction.transaction_status} />
                </dd>
              </div>
              <div className="field">
                <dt className="field__label">Amount</dt>
                <dd className="field__value">
                  {formatAmount(
                    result.verified_transaction.amount,
                    result.verified_transaction.currency,
                  )}
                </dd>
              </div>
              <div className="field">
                <dt className="field__label">Recorded</dt>
                <dd className="field__value">
                  {formatDateTime(result.verified_transaction.transaction_date)}
                </dd>
              </div>
              <div className="field">
                <dt className="field__label">Response code</dt>
                <dd className="field__value">
                  {result.verified_transaction.response_code === null ? (
                    <span className="muted">{NOT_RECORDED}</span>
                  ) : (
                    <span className="muted">
                      <code className="code">{result.verified_transaction.response_code}</code>{" "}
                      unexplained
                    </span>
                  )}
                </dd>
              </div>
            </dl>
          </>
        )}
      </Card>

      {shown.caseOpened && result.support_case !== null && (
        <Card title="Your support case">
          <dl className="fields fields--wide">
            <div className="field">
              <dt className="field__label">Reference</dt>
              <dd className="field__value">
                <code className="code">{caseReference(result.support_case.case_id)}</code>
              </dd>
            </div>
            <div className="field">
              <dt className="field__label">Status</dt>
              <dd className="field__value">{humanize(result.support_case.status)}</dd>
            </div>
            <div className="field">
              <dt className="field__label">Sent to</dt>
              <dd className="field__value">{humanize(result.support_case.recommended_route)}</dd>
            </div>
            <div className="field">
              <dt className="field__label">Opened</dt>
              <dd className="field__value">{formatDateTime(result.support_case.created_at)}</dd>
            </div>
          </dl>
        </Card>
      )}

      <Card title="How this was decided">
        {loadingTimeline ? (
          <Loading label="Loading the recorded steps" />
        ) : (
          <ol className="steps">
            {steps.map((step) => (
              <li key={step.key} className={`steps__step steps__step--${step.state}`}>
                <span className="steps__marker" aria-hidden="true" />
                <div>
                  <p className="steps__label">{step.label}</p>
                  {step.detail !== null && <p className="steps__detail">{step.detail}</p>}
                  <span className="visually-hidden">{stateWord(step.state)}</span>
                </div>
              </li>
            ))}
          </ol>
        )}

        {timelineError !== null && (
          <ErrorNotice title="The recorded steps could not be read">
            <p>{timelineError}</p>
          </ErrorNotice>
        )}
      </Card>

      <div className="button-row">
        <Link className="button button--primary" to="/">
          Back to overview
        </Link>
        <Link className="button button--quiet" to="/movements">
          Review all movements
        </Link>
      </div>
    </>
  );
}

function stateWord(state: string): string {
  return state === "done" ? "Done" : state === "failed" ? "Failed" : "Not reached";
}

import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import type { ClarificationCandidate, TransactionFilters } from "../api/types";
import { Card, ErrorNotice, Loading } from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { formatAmount, formatDateTime, humanize } from "../lib/format";
import { useIncidents } from "../state/IncidentProvider";
import { useSession } from "../state/SessionProvider";

const TYPES = ["Transfer", "Payment", "Withdrawal", "Deposit", "Purchase", "Adjustment"];
const CURRENCIES = ["USD", "ARS", "COP"];
const CHANNELS = ["App", "Web", "ATM", "POS", "Transfer", "Branch"];

/**
 * Reporting an issue.
 *
 * Two ways in, matching the two things a customer can actually know:
 *
 * - `/report/:transactionId` for a movement they are already looking at.
 * - `/report` when they are not sure, which searches on what they do remember and hands the
 *   candidates back rather than choosing one for them.
 *
 * There is no free-text box. The customer describes the problem by choosing a movement, and the
 * policy decides what happens next from the recorded status alone.
 */
export function ReportIssueView() {
  const { transactionId } = useParams();
  const { api, endSession } = useSession();
  const { record } = useIncidents();
  const navigate = useNavigate();

  const [unresolvedApproved, setUnresolvedApproved] = useState(false);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const load = useCallback((client: typeof api) => client.getTransactions(), [api]);
  const { data, error, loading, reload } = useResource(api, load, endSession);

  const movements = data?.transactions ?? [];
  const exact = transactionId !== undefined && transactionId !== "";
  const selected = exact ? (movements.find((row) => row.transaction_id === transactionId) ?? null) : null;

  async function submit(payload: Record<string, unknown>, key: string): Promise<void> {
    setSubmitting(key);
    setSubmitError(null);
    try {
      const outcome = await api.reportIncident(payload);
      record(outcome);
      navigate(`/resolution/${outcome.incident_id}`, { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.isSessionGone) {
        endSession();
        return;
      }
      setSubmitError(caught instanceof Error ? caught.message : "The report could not be sent.");
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <main className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Report an issue</p>
          <h1 className="page__title">{exact ? "This movement" : "Which movement is it?"}</h1>
        </div>
      </header>

      {error !== null && (
        <ErrorNotice title="We could not load your movements" onRetry={reload}>
          <p>{error}</p>
        </ErrorNotice>
      )}

      {loading && <Loading label="Loading your movements" />}

      {submitError !== null && (
        <ErrorNotice title="The report could not be sent" onDismiss={() => setSubmitError(null)}>
          <p>{submitError}</p>
        </ErrorNotice>
      )}

      {exact && selected !== null && (
        <Card title="Check this movement">
          <p className="muted">
            We will check this exact movement against our records. You do not need to explain why it
            is wrong.
          </p>

          {selected.transaction_status === "Approved" && (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={unresolvedApproved}
                onChange={(event) => setUnresolvedApproved(event.target.checked)}
              />
              <span>This movement went through, but the problem I am reporting is still not fixed</span>
            </label>
          )}

          <div className="button-row">
            <button
              type="button"
              className="button button--primary"
              disabled={submitting !== null}
              onClick={() =>
                void submit(
                  {
                    transaction_id: selected.transaction_id,
                    approved_with_unresolved_issue: unresolvedApproved,
                  },
                  selected.transaction_id,
                )
              }
            >
              {submitting === selected.transaction_id ? "Checking…" : "Check this movement"}
            </button>
            <button
              type="button"
              className="button button--quiet"
              disabled={submitting !== null}
              onClick={() => void submit({ transaction_id: selected.transaction_id, in_scope: false }, "out-of-scope")}
            >
              This is not a problem with my account
            </button>
          </div>
        </Card>
      )}

      {exact && !loading && selected === null && (
        <Card title="Check this movement">
          <p className="muted">That movement is not on your record, so we cannot check it.</p>
          <Link className="button button--primary" to="/report">
            Search all of your movements
          </Link>
        </Card>
      )}

      {!exact && movements.length > 0 && (
        <AmbiguitySearch movements={movements} onSubmit={submit} submitting={submitting} />
      )}

      {exact && movements.length > 0 && (
        <Card title="Not this one?">
          <Link className="button button--quiet" to="/report">
            Search all of your movements instead
          </Link>
        </Card>
      )}
    </main>
  );
}

/**
 * The ambiguity path.
 *
 * Submitting the filters runs the real policy, not a local search. If more than one movement
 * matches, the workflow returns a clarification and nothing is decided; if exactly one matches,
 * that movement is verified and the outcome follows its recorded status.
 */
function AmbiguitySearch({
  movements,
  onSubmit,
  submitting,
}: {
  movements: ClarificationCandidate[];
  onSubmit: (payload: Record<string, unknown>, key: string) => Promise<void>;
  submitting: string | null;
}) {
  const [filters, setFilters] = useState<TransactionFilters>({});

  function set(key: keyof TransactionFilters, value: string): void {
    setFilters((current) => ({ ...current, [key]: value === "" ? undefined : value }));
  }

  const active = Object.entries(filters).filter(([, value]) => value !== undefined && value !== "");
  const busy = submitting === "search";

  return (
    <>
      <Card title="Describe what you remember">
        <p className="muted">
          Narrow it down as much as you can. If more than one movement is left, we will show you the
          options rather than guess which one you meant.
        </p>
        <div className="filters">
          <Select
            id="report-type"
            label="Type"
            value={filters.transaction_type ?? ""}
            options={TYPES}
            onChange={(value) => set("transaction_type", value)}
          />
          <Select
            id="report-currency"
            label="Currency"
            value={filters.currency ?? ""}
            options={CURRENCIES}
            onChange={(value) => set("currency", value)}
          />
          <Select
            id="report-channel"
            label="Channel"
            value={filters.channel ?? ""}
            options={CHANNELS}
            onChange={(value) => set("channel", value)}
          />
          <div className="filters__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={submitting !== null}
              onClick={() => void onSubmit({ filters: Object.fromEntries(active) }, "search")}
            >
              {busy ? "Searching…" : "Find my movement"}
            </button>
          </div>
        </div>
      </Card>

      <Card title={`All ${movements.length} on record`}>
        <ul className="candidates">
          {movements.map((row) => (
            <li key={row.transaction_id}>
              <CandidateRow row={row} onSubmit={onSubmit} submitting={submitting} />
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

/** One candidate. Choosing it is what narrows the question to a single movement. */
function CandidateRow({
  row,
  onSubmit,
  submitting,
}: {
  row: ClarificationCandidate;
  onSubmit: (payload: Record<string, unknown>, key: string) => Promise<void>;
  submitting: string | null;
}) {
  const busy = submitting === row.transaction_id;
  return (
    <div className="candidate">
      <div>
        <p className="candidate__type">{humanize(row.transaction_type)}</p>
        <p className="candidate__meta">
          {formatAmount(row.amount, row.currency)} · {formatDateTime(row.transaction_date)}
        </p>
      </div>
      <div className="candidate__side">
        <span className="chip">{humanize(row.transaction_status)}</span>
        <button
          type="button"
          className="button button--quiet"
          disabled={submitting !== null}
          onClick={() => void onSubmit({ transaction_id: row.transaction_id }, row.transaction_id)}
        >
          {busy ? "Checking…" : "This one"}
        </button>
      </div>
    </div>
  );
}

function Select({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="control">
      <label className="control__label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="control__input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
import { useCallback } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { Transaction } from "../api/types";
import { Card, ErrorNotice, Field, Loading, StatusPill } from "../components/primitives";
import { useResource } from "../hooks/useResource";
import { formatAmount, formatDate, formatDateTime, humanize, NOT_RECORDED } from "../lib/format";
import { useSession } from "../state/SessionProvider";

/**
 * Movement detail.
 *
 * Everything on this screen is a field the backend returned for this exact movement. The response
 * code is shown verbatim and labelled as unexplained, because the curated data carries no meaning
 * for it and we will not invent one.
 */
export function MovementDetailView() {
  const { transactionId = "" } = useParams();
  const { api, endSession } = useSession();
  const navigate = useNavigate();

  const load = useCallback(
    (client: typeof api) => client.getTransaction(transactionId),
    [api, transactionId],
  );
  const { data, error, loading, reload } = useResource(api, load, endSession);

  const transaction: Transaction | null = data;

  return (
    <main className="page">
      <nav aria-label="Breadcrumb" className="breadcrumb">
        <Link to="/movements">← All movements</Link>
      </nav>

      {loading && <Loading label="Loading this movement" />}

      {error !== null && (
        <ErrorNotice title="We could not open this movement" onRetry={reload}>
          <p>{error}</p>
        </ErrorNotice>
      )}

      {transaction !== null && (
        <>
          <header className="page__header">
            <div>
              <p className="eyebrow">{humanize(transaction.transaction_type)}</p>
              <h1 className="page__title">{formatAmount(transaction.amount, transaction.currency)}</h1>
            </div>
            <StatusPill status={transaction.transaction_status} />
          </header>

          <StatusExplainer status={transaction.transaction_status} />

          <Card title="What our records show">
            <dl className="fields fields--wide">
              <Field label="Status">
                <StatusPill status={transaction.transaction_status} />
              </Field>
              <Field label="Type">{humanize(transaction.transaction_type)}</Field>
              <Field label="Amount">{formatAmount(transaction.amount, transaction.currency)}</Field>
              <Field label="Amount in USD">
                {transaction.amount_usd === null ? (
                  <span className="muted">{NOT_RECORDED}</span>
                ) : (
                  formatAmount(transaction.amount_usd, "USD")
                )}
              </Field>
              <Field label="Recorded">{formatDateTime(transaction.transaction_date)}</Field>
              <Field label="Processed">{formatDate(transaction.process_date)}</Field>
              <Field label="Channel">{humanize(transaction.channel)}</Field>
              <Field label="Response code">
                {transaction.response_code === null ? (
                  <span className="muted">{NOT_RECORDED}</span>
                ) : (
                  <>
                    <code className="code">{transaction.response_code}</code>
                    <span className="hint">
                      Our records carry this code but no meaning for it, so we cannot tell you what it
                      stands for.
                    </span>
                  </>
                )}
              </Field>
            </dl>
          </Card>

          <Card title="Something not right?">
            <p className="muted">
              Tell us about this exact movement. We will check it against our records and either
              answer from them or pass it to a specialist.
            </p>
            <div className="button-row">
              <button
                type="button"
                className="button button--primary"
                onClick={() => navigate(`/report/${encodeURIComponent(transaction.transaction_id)}`)}
              >
                Report an issue with this movement
              </button>
              <Link className="button button--quiet" to="/report">
                I am not sure which movement
              </Link>
            </div>
          </Card>
        </>
      )}
    </main>
  );
}

/**
 * Says what the recorded status does and does not mean.
 *
 * This is the difference the whole prototype exists to make: a declined movement is a final answer,
 * a reversed one is not a refund confirmation, and a pending one has not settled.
 */
function StatusExplainer({ status }: { status: string }) {
  const copy: Record<string, string> = {
    declined:
      "This movement was declined. We hold no reason for the decline, and we will not guess at one.",
    pending:
      "This movement is still in progress. It has not settled, so we cannot tell you where the money is yet.",
    reversed:
      "This movement was reversed. That does not by itself confirm the money reached your account.",
    approved: "This movement is recorded as approved.",
  };
  const text = copy[status.toLowerCase()];
  if (text === undefined) {
    return null;
  }
  return (
    <p className="explainer" role="note">
      {text}
    </p>
  );
}
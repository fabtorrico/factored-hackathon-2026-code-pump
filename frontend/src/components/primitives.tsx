import type { ReactNode } from "react";

import type { OutcomeTone } from "../lib/outcome";
import { humanize } from "../lib/format";

/**
 * Status pill.
 *
 * Colour is never the only signal: the label always carries the curated status word, so the pill
 * stays readable without colour and under any contrast setting.
 */
export function StatusPill({ status, tone }: { status: string; tone?: OutcomeTone }) {
  const resolved = toneFor(status, tone);
  return (
    <span className={`pill pill--${resolved}`}>
      <span className="pill__dot" aria-hidden="true" />
      {humanize(status)}
    </span>
  );
}

/** The outcome pill, which carries a policy word rather than a curated status. */
export function OutcomePill({ label, tone }: { label: string; tone: OutcomeTone }) {
  return (
    <span className={`pill pill--${tone}`}>
      <span className="pill__dot" aria-hidden="true" />
      {label}
    </span>
  );
}

const STATUS_TONES: Record<string, OutcomeTone> = {
  approved: "positive",
  active: "positive",
  resolved: "positive",
  declined: "attention",
  pending: "attention",
  attention: "attention",
  reversed: "attention",
  blocked: "critical",
  failed: "critical",
  closed: "neutral",
};

function toneFor(status: string, override: OutcomeTone | undefined): OutcomeTone {
  if (override !== undefined) {
    return override;
  }
  return STATUS_TONES[status.toLowerCase()] ?? "neutral";
}

export function Card({
  title,
  children,
  actions,
}: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="card">
      {(title !== undefined || actions !== undefined) && (
        <header className="card__header">
          {title !== undefined && <h2 className="card__title">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty__title">{title}</p>
      {children}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="loading" role="status">
      <span className="loading__bar" aria-hidden="true" />
      <span className="loading__bar" aria-hidden="true" />
      <span className="loading__bar" aria-hidden="true" />
      <span className="visually-hidden">{label}</span>
    </div>
  );
}

/**
 * Error notice.
 *
 * Shows the backend's own message rather than a generic apology, and never guesses at what went
 * wrong. `role="alert"` so a screen reader announces it as soon as it appears.
 */
export function ErrorNotice({
  title,
  children,
  onRetry,
  onDismiss,
}: {
  title: string;
  children?: ReactNode;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <div className="notice notice--critical" role="alert">
      <div>
        <p className="notice__title">{title}</p>
        {children !== undefined && <div className="notice__body">{children}</div>}
      </div>
      <div className="notice__actions">
        {onRetry !== undefined && (
          <button type="button" className="button button--quiet" onClick={onRetry}>
            Try again
          </button>
        )}
        {onDismiss !== undefined && (
          <button type="button" className="button button--quiet" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}

/** A labelled value, used everywhere a single fact is shown. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field">
      <dt className="field__label">{label}</dt>
      <dd className="field__value">{children}</dd>
    </div>
  );
}
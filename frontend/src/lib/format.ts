/**
 * Display formatting. Every function here is total: a missing or unparseable value becomes a
 * visible "not recorded" marker rather than a zero, a blank, or an invented number.
 */

export const NOT_RECORDED = "Not recorded";

/** Formats an amount with its currency, grouped for readability. */
export function formatAmount(amount: number | null | undefined, currency: string | null): string {
  if (amount === null || amount === undefined || !Number.isFinite(amount)) {
    return NOT_RECORDED;
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency && currency.length === 3 ? currency : "USD",
      currencyDisplay: "code",
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency ?? ""}`.trim();
  }
}

const DATE_TIME = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const DATE_ONLY = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

/** A timestamp the curated data recorded, shown to the minute. */
export function formatDateTime(value: string | null | undefined): string {
  const parsed = parse(value);
  return parsed === null ? NOT_RECORDED : DATE_TIME.format(parsed);
}

/** A date without a time, for the process date the curated data stores as a day. */
export function formatDate(value: string | null | undefined): string {
  const parsed = parse(value);
  return parsed === null ? NOT_RECORDED : DATE_ONLY.format(parsed);
}

function parse(value: string | null | undefined): Date | null {
  if (typeof value !== "string" || value === "") {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Turns a curated token into readable words without ever changing its meaning. */
export function humanize(value: string | null | undefined): string {
  if (typeof value !== "string" || value.trim() === "") {
    return NOT_RECORDED;
  }
  const spaced = value.replace(/[_-]+/g, " ").trim();
  const capitalised = spaced.charAt(0).toUpperCase() + spaced.slice(1);
  // An internal code like PAYMENTS_OPERATIONS reads as a sentence; a curated value like
  // "Cuenta Corriente" keeps its own capitalisation, because lowering it would change it.
  return spaced === spaced.toUpperCase()
    ? capitalised.charAt(0).toUpperCase() + capitalised.slice(1).toLowerCase()
    : capitalised;
}

/** A short, human reference. Curated identifiers stay internal, so this only shortens a case id. */
export function shortReference(value: string | null | undefined): string {
  if (typeof value !== "string" || value === "") {
    return NOT_RECORDED;
  }
  return value.length <= 12 ? value : `${value.slice(0, 8)}…${value.slice(-4)}`;
}
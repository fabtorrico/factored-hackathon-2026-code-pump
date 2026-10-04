import { NOT_RECORDED } from "./format";

/**
 * Short, human references for persisted identifiers.
 *
 * A support case id and an incident id are both 36-character UUIDs. They stay whole in the data and
 * in the agent URL, but on screen they are shown as a short, stable, prefixed form so a person can
 * read and compare them. The prefix says which kind of identifier it is, so a case reference and an
 * incident reference can never be mistaken for one another.
 */

function label(prefix: string, value: string | null | undefined): string {
  if (typeof value !== "string") {
    return NOT_RECORDED;
  }
  const compact = value.replace(/[^a-zA-Z0-9]/g, "");
  if (compact === "") {
    return NOT_RECORDED;
  }
  return `${prefix} ${compact.slice(0, 8).toUpperCase()}`;
}

/** A support case's short reference, for both the customer and the agent surface. */
export function caseReference(caseId: string | null | undefined): string {
  return label("CASE", caseId);
}

/** An incident's short reference. */
export function incidentReference(incidentId: string | null | undefined): string {
  return label("INCIDENT", incidentId);
}

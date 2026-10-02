import { describe, expect, it } from "vitest";

import { formatAmount, formatDate, formatDateTime, humanize, NOT_RECORDED, shortReference } from "./format";

/**
 * A missing curated value must stay visibly missing. Formatting it as 0, an empty string or
 * "Invalid Date" would put an invented fact on the screen.
 */

describe("amounts", () => {
  it("formats a real amount with its currency", () => {
    expect(formatAmount(345.41, "USD")).toContain("345.41");
    expect(formatAmount(345.41, "USD")).toContain("USD");
  });

  it("says so when there is no amount", () => {
    expect(formatAmount(null, "USD")).toBe(NOT_RECORDED);
    expect(formatAmount(undefined, "USD")).toBe(NOT_RECORDED);
    expect(formatAmount(Number.NaN, "USD")).toBe(NOT_RECORDED);
  });

  it("still shows the amount when the currency is unusable", () => {
    expect(formatAmount(12.5, null)).toContain("12.50");
  });
});

describe("timestamps", () => {
  it("formats a recorded moment", () => {
    expect(formatDateTime("2026-06-17T06:35:58")).toMatch(/2026/);
  });

  it("says so when nothing was recorded", () => {
    expect(formatDateTime(null)).toBe(NOT_RECORDED);
    expect(formatDateTime("")).toBe(NOT_RECORDED);
    expect(formatDateTime("not a date")).toBe(NOT_RECORDED);
    expect(formatDate(null)).toBe(NOT_RECORDED);
  });

  it("does not render Invalid Date", () => {
    expect(formatDateTime("2026-13-45")).toBe(NOT_RECORDED);
  });
});

describe("curated tokens", () => {
  it("makes them readable without changing the meaning", () => {
    expect(humanize("PAYMENTS_OPERATIONS")).toBe("Payments operations");
    expect(humanize("Cuenta Corriente")).toBe("Cuenta Corriente");
  });

  it("says so for a missing token", () => {
    expect(humanize(null)).toBe(NOT_RECORDED);
    expect(humanize("   ")).toBe(NOT_RECORDED);
  });
});

describe("references", () => {
  it("shortens a long identifier", () => {
    const reference = shortReference("45105b30-e998-4531-8c2a-2cfe28ff27e0");
    expect(reference).toHaveLength(13);
    expect(reference).toContain("…");
  });

  it("leaves a short one alone", () => {
    expect(shortReference("CASE-1")).toBe("CASE-1");
    expect(shortReference(null)).toBe(NOT_RECORDED);
  });
});
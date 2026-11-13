// Display helpers. They only FORMAT values the API sent; they never compute a benchmark metric.
import type { Rate } from "./api/client";

/** "2026-11-13 09:34 UTC" - the same UTC times the CLI reports, so both always agree. */
export function utc(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

/** A number from the API, or "n/a" when the API says it is unknown (null) - never a fake 0. */
export function num(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(digits);
}

/** "6 / 10" exactly as counted by the server (no percentage is calculated in the browser). */
export function counts(rate: Rate | null | undefined): string {
  return rate ? `${rate.passed} / ${rate.eligible}` : "n/a";
}

export function short(id: string): string {
  return id.slice(0, 8);
}

// Chart data: PURE functions that only RESHAPE what the API sent (pick, order, label).
// They never calculate a benchmark metric - every number shown comes from the server unchanged.
import type { HistoryEntry } from "../api/client";
import { utc } from "../format";

export type CategoryBar = { category: string; runs: number };

/** {"wrong_result": 4, "loop": 1} -> bars, in the SERVER's order (which is the analyzer's priority order).
 *  Only agent-failure categories are in category_counts; infrastructure errors never appear here. */
export function categoryBars(counts: Record<string, number> | undefined): CategoryBar[] {
  return Object.entries(counts ?? {}).map(([category, runs]) => ({ category, runs }));
}

export type HistoryBar = {
  key: string;
  label: string;           // when + which run, for the axis and the table
  llmCalls: number | null; // null = not executed (skipped): drawn as no bar, never as 0
  outcome: string;
  suiteId: string;
};

/** History entries (the server sends newest first) -> bars, oldest first so time reads left to right. */
export function historyBars(items: HistoryEntry[]): HistoryBar[] {
  return [...items].reverse().map((h, i) => ({
    key: `${h.suite_id}-${h.repeat}-${i}`,
    label: `${utc(h.started_at).slice(5, 16)} · ${h.suite_id.slice(0, 8)}${h.repeat > 0 ? ` #${h.repeat + 1}` : ""}`,
    llmCalls: h.llm_calls ?? null,
    outcome: h.outcome,
    suiteId: h.suite_id,
  }));
}

export const OUTCOME_COLOR: Record<string, string> = {
  passed: "#059669", failed: "#dc2626", infra_error: "#d97706", skipped: "#94a3b8",
};

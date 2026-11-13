// Pass-rate-over-time: PURE functions that only reshape the run list for the chart.
// Rules (user-approved, Step 10.3b):
//   * a point may be on a line ONLY if registration_status = matches, scope = full and complete = true;
//   * lines never cross groups: suite + provider + model + config fingerprint + tools fingerprint + kind;
//     an unknown (null) tools fingerprint is its own group, never merged with a known one;
//   * every other run is a separate, unconnected marker, with the reason;
//   * the value is the server's pass_rate.rate, unchanged; null = no point (never 0%).
import type { SuiteSummary } from "../api/client";

export type MarkerKind = "incomplete" | "differs" | "subset" | "unregistered" | "unknown";

export type TrendPoint = {
  suiteId: string;
  shortId: string;
  x: number;              // start time (ms) - only for placing the point on the time axis
  rate: number;           // the server's pass_rate.rate, unchanged
  rateText: string;       // the server's own text, e.g. "2/2 (100.0%)"
  startedAt: string;
  group: string;          // the six-part key
  groupLabel: string;
  reasons: string[];      // why it is NOT on a line ([] = eligible)
  marker: MarkerKind | null;
};

export type TrendGroup = { key: string; label: string; points: TrendPoint[]; baseline: boolean };

export type TrendData = {
  groups: TrendGroup[];              // eligible points only, sorted by time, one line per group
  markers: TrendPoint[];             // ineligible points (never connected)
  noValue: SuiteSummary[];           // rate === null: nothing evaluated -> no point at all
  hiddenScripted: number;
};

// Known tools are written "tools=<fingerprint>", unknown tools "tools-not-recorded": the two FORMATS differ,
// so an unknown can never equal any known fingerprint (not even one literally named "unknown").
const UNKNOWN_TOOLS = "tools-not-recorded";

export function groupKey(s: SuiteSummary): string {
  return [s.suite_name, s.provider, s.model, `config=${s.config_fingerprint}`,
          s.tools_fingerprint ? `tools=${s.tools_fingerprint}` : UNKNOWN_TOOLS, s.kind].join("|");
}

export function groupLabel(s: SuiteSummary): string {
  const tools = s.tools_fingerprint ? `tools ${s.tools_fingerprint.slice(0, 8)}` : "tools unknown";
  return `${s.suite_name} · ${s.kind === "real" ? s.model : `SCRIPTED ${s.model}`} · config ${s.config_fingerprint.slice(0, 8)} · ${tools}`;
}

/** Why a run may not be connected to a full-suite trend ([] = it may). */
export function ineligibility(s: SuiteSummary): string[] {
  const reasons: string[] = [];
  if (!s.complete) reasons.push("incomplete");
  if (s.registration_status === "differs") reasons.push("differs from registration");
  if (s.scope === "subset") reasons.push("subset (not a full-suite score)");
  if (s.registration_status === "unregistered") reasons.push("unregistered suite");
  if (s.scope === "unknown" || s.registration_status === "unknown") reasons.push("task set unknown");
  if (reasons.length === 0 && !(s.registration_status === "matches" && s.scope === "full")) reasons.push("not comparable");
  return reasons;
}

function markerOf(s: SuiteSummary): MarkerKind {
  if (!s.complete) return "incomplete";
  if (s.registration_status === "differs") return "differs";
  if (s.scope === "subset") return "subset";
  if (s.registration_status === "unregistered") return "unregistered";
  return "unknown";
}

export function buildTrend(items: SuiteSummary[], { includeScripted = false } = {}): TrendData {
  const visible = items.filter((s) => includeScripted || s.kind === "real");
  const byGroup = new Map<string, TrendGroup>();
  const markers: TrendPoint[] = [];
  const noValue: SuiteSummary[] = [];
  for (const s of visible) {
    const rate = s.pass_rate.rate;
    if (rate === null || rate === undefined) {
      noValue.push(s);                                    // nothing evaluated: no point, never 0%
      continue;
    }
    const reasons = ineligibility(s);
    const point: TrendPoint = {
      suiteId: s.suite_id, shortId: s.short_id, x: Date.parse(s.started_at), rate, rateText: s.pass_rate.text,
      startedAt: s.started_at, group: groupKey(s), groupLabel: groupLabel(s), reasons,
      marker: reasons.length ? markerOf(s) : null,
    };
    if (reasons.length) {
      markers.push(point);
      continue;
    }
    const group = byGroup.get(point.group) ?? { key: point.group, label: point.groupLabel, points: [], baseline: false };
    group.points.push(point);
    byGroup.set(point.group, group);
  }
  const groups = [...byGroup.values()].map((g) => {
    const points = [...g.points].sort((a, b) => a.x - b.x);   // each group sorted on its own
    return { ...g, points, baseline: points.length === 1 };   // one run = a baseline, not a trend
  });
  return { groups, markers: markers.sort((a, b) => a.x - b.x), noValue,
           hiddenScripted: items.length - visible.length };
}

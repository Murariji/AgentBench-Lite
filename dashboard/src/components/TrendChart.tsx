// Pass rate over time (top of the Runs page). Each comparable group is its OWN series (own line);
// every non-comparable run is a separate, unconnected marker. Values are the server's, unchanged.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CartesianGrid, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_RUN_LIMIT, type ChartRuns } from "../api/client";
import type { ApiState } from "../api/useApi";
import { buildTrend, type MarkerKind, type TrendPoint } from "../charts/trend";
import { utc } from "../format";
import { Card, Loaded } from "./ui";
import { useWidth } from "./useWidth";

const LINE_COLORS = ["rgb(var(--accent))", "rgb(var(--info-fg))", "rgb(var(--success-fg))", "rgb(var(--warning-fg))", "rgb(var(--danger-fg))"];
const MARKERS: Record<MarkerKind, { label: string; shape: "circle" | "cross" | "square" | "triangle" | "diamond"; color: string }> = {
  subset: { label: "subset (not a full-suite score)", shape: "circle", color: "rgb(var(--chart-mark))" },
  differs: { label: "differs from registration", shape: "cross", color: "rgb(var(--danger-fg))" },
  unregistered: { label: "unregistered suite", shape: "square", color: "rgb(var(--neutral-fg))" },
  incomplete: { label: "incomplete", shape: "triangle", color: "rgb(var(--warning-fg))" },
  unknown: { label: "task set unknown", shape: "diamond", color: "rgb(var(--muted))" },
};

/** Evenly spaced time ticks with a small margin, so no point sits on the chart's edge (axis labels only). */
export function timeAxis(xs: number[], count = 6): { domain: [number, number]; ticks: number[] } {
  const min = Math.min(...xs), max = Math.max(...xs);
  const pad = max > min ? (max - min) * 0.04 : 3_600_000;
  const lo = min - pad, hi = max + pad;
  return { domain: [lo, hi], ticks: Array.from({ length: count }, (_, i) => Math.round(lo + ((hi - lo) * i) / (count - 1))) };
}

function Shape({ shape, color }: { shape: string; color: string }) {
  const p = { fill: color };
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="flex-none">
      {shape === "circle" && <circle cx="6" cy="6" r="5" {...p} />}
      {shape === "square" && <rect x="1" y="1" width="10" height="10" {...p} />}
      {shape === "diamond" && <polygon points="6,0 12,6 6,12 0,6" {...p} />}
      {shape === "triangle" && <polygon points="6,1 11,11 1,11" {...p} />}
      {shape === "cross" && <path d="M2 2l8 8M10 2l-8 8" stroke={color} strokeWidth="2.5" />}
      {shape === "line" && <><line x1="0" y1="6" x2="12" y2="6" stroke={color} strokeWidth="2" /><circle cx="6" cy="6" r="3.5" {...p} /></>}
    </svg>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;      // axis LABEL only; the plotted value is unchanged

function Tip({ active, payload }: { active?: boolean; payload?: { payload: TrendPoint }[] }) {
  const p = active ? payload?.[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rounded border border-border bg-surface p-2 text-[13px] shadow">
      <p className="font-mono font-semibold">{p.shortId}</p>
      <p>{utc(p.startedAt)}</p>
      <p>pass rate {p.rateText}</p>
      <p className="text-muted">{p.groupLabel}</p>
      <p>{p.reasons.length ? `not on a trend line: ${p.reasons.join(", ")}` : "comparable full-suite run"}</p>
    </div>
  );
}

/** `runs` is loaded ONCE by the page (fetchRunsForChart) and shared with the page's table. */
export function TrendChart({ runs }: { runs: ApiState<ChartRuns> & { reload: () => void } }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [includeScripted, setIncludeScripted] = useState(false);
  const navigate = useNavigate();
  const open = (p: unknown) => {
    const id = (p as { payload?: TrendPoint })?.payload?.suiteId;
    if (id) navigate(`/suites/${id}`);
  };

  return (
    <Card title="Pass rate over time">
      <Loaded state={runs}>
        {({ items, total, capped }) => {
          const t = buildTrend(items, { includeScripted });
          const allPoints = [...t.groups.flatMap((g) => g.points), ...t.markers];
          const lines = t.groups.filter((g) => !g.baseline);
          const summary = t.groups.length === 0
            ? `No comparable full-suite runs yet; ${t.markers.length} run(s) shown as separate markers.`
            : `${t.groups.length} comparable group(s): ${t.groups.map((g) => `${g.label} - ${g.baseline ? "first comparable full-suite baseline" : `${g.points.length} runs`}`).join("; ")}. ${t.markers.length} other run(s) as separate markers.`;
          return (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={includeScripted} onChange={(e) => setIncludeScripted(e.target.checked)} />
                  Include SCRIPTED runs (test fixtures, not AI)
                </label>
                {capped && (
                  <span role="note" className="rounded bg-warning-bg px-2 py-0.5 text-warning-fg">
                    Showing only the latest {CHART_RUN_LIMIT} of {total} runs.
                  </span>
                )}
              </div>

              {t.groups.length === 0 && (
                <p role="note" className="rounded border border-border bg-surface-2 p-2 text-sm">
                  No comparable full-suite runs yet (registered, full suite, complete), so there is no trend line. Every
                  run below is a separate marker. A complete, full-suite run that matches its registration would be the first
                  comparable full-suite baseline - whether a given run qualifies is known only after it has run.
                </p>
              )}
              {t.groups.some((g) => g.baseline) && (
                <p className="text-sm text-muted">
                  A group with one run shows a first comparable full-suite baseline, not a trend.
                </p>
              )}

              {allPoints.length > 0 && (
                <div ref={box} className="overflow-x-auto" role="img" aria-label={summary}>
                  <ScatterChart width={width} height={300} margin={{ top: 20, right: 24, bottom: 8, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="x" {...timeAxis(allPoints.map((p) => p.x))} name="started"
                           tickFormatter={(v: number) => utc(new Date(v).toISOString()).slice(5, 16)} tick={{ fontSize: 12 }} />
                    <YAxis type="number" dataKey="rate" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={pct}
                           name="pass rate" tick={{ fontSize: 12 }} width={48} />
                    <Tooltip content={<Tip />} />
                    {t.groups.map((g, i) => (
                      <Scatter key={g.key} name={g.baseline ? `${g.label} (baseline)` : g.label} data={g.points}
                               line={!g.baseline} fill={LINE_COLORS[i % LINE_COLORS.length]} isAnimationActive={false}
                               onClick={open} />
                    ))}
                    {(Object.keys(MARKERS) as MarkerKind[]).map((kind) => {
                      const data = t.markers.filter((m) => m.marker === kind);
                      return data.length ? (
                        <Scatter key={kind} name={MARKERS[kind].label} data={data} shape={MARKERS[kind].shape}
                                 fill={MARKERS[kind].color} isAnimationActive={false} onClick={open} />
                      ) : null;
                    })}
                  </ScatterChart>
                </div>
              )}
              {allPoints.length > 0 && (
                <ul aria-label="legend" className="flex flex-wrap gap-x-5 gap-y-1.5 text-[13px]">
                  {t.groups.map((g, i) => (
                    <li key={g.key} className="flex items-center gap-1.5">
                      <Shape shape="line" color={LINE_COLORS[i % LINE_COLORS.length]!} />{g.baseline ? `${g.label} (baseline)` : g.label}
                    </li>
                  ))}
                  {(Object.keys(MARKERS) as MarkerKind[]).filter((k) => t.markers.some((m) => m.marker === k)).map((k) => (
                    <li key={k} className="flex items-center gap-1.5"><Shape shape={MARKERS[k].shape} color={MARKERS[k].color} />{MARKERS[k].label}</li>
                  ))}
                </ul>
              )}

              <details className="text-sm">
                <summary className="cursor-pointer text-muted">Data table ({allPoints.length} points{lines.length ? `, ${lines.length} line(s)` : ""})</summary>
                <table className="mt-2 w-full text-left text-[13px]" aria-label="pass rate over time (data)">
                  <thead className="uppercase text-muted">
                    <tr><th className="pr-2">Run</th><th className="pr-2">Started</th><th className="pr-2">Pass rate</th><th className="pr-2">Group</th><th>On a trend line?</th></tr>
                  </thead>
                  <tbody>
                    {allPoints.sort((a, b) => a.x - b.x).map((p) => (
                      <tr key={p.suiteId} className="border-t border-border">
                        <td className="pr-2 font-mono">{p.shortId}</td><td className="pr-2">{utc(p.startedAt)}</td>
                        <td className="pr-2">{p.rateText}</td><td className="pr-2">{p.groupLabel}</td>
                        <td>{p.reasons.length ? `no - ${p.reasons.join(", ")}` : "yes"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
              {t.noValue.length > 0 && (
                <p className="text-[13px] text-muted">
                  Not plotted (no evaluated runs, so no pass rate - never shown as 0%): {t.noValue.map((s) => s.short_id).join(", ")}
                </p>
              )}
              {!includeScripted && t.hiddenScripted > 0 && (
                <p className="text-[13px] text-muted">{t.hiddenScripted} scripted run(s) hidden.</p>
              )}
            </div>
          );
        }}
      </Loaded>
    </Card>
  );
}

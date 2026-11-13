// Pass rate over time (top of the Runs page). Each comparable group is its OWN series (own line);
// every non-comparable run is a separate, unconnected marker. Values are the server's, unchanged.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CartesianGrid, Legend, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { CHART_RUN_LIMIT, fetchRunsForChart } from "../api/client";
import { useApi } from "../api/useApi";
import { buildTrend, type MarkerKind, type TrendPoint } from "../charts/trend";
import { utc } from "../format";
import { Card, Loaded } from "./ui";

const LINE_COLORS = ["#0369a1", "#7c3aed", "#059669", "#b45309", "#be123c"];
const MARKERS: Record<MarkerKind, { label: string; shape: "circle" | "cross" | "square" | "triangle" | "diamond"; color: string }> = {
  subset: { label: "subset (not a full-suite score)", shape: "circle", color: "#d97706" },
  differs: { label: "differs from registration", shape: "cross", color: "#dc2626" },
  unregistered: { label: "unregistered suite", shape: "square", color: "#64748b" },
  incomplete: { label: "incomplete", shape: "triangle", color: "#f59e0b" },
  unknown: { label: "task set unknown", shape: "diamond", color: "#94a3b8" },
};

const pct = (v: number) => `${Math.round(v * 100)}%`;      // axis LABEL only; the plotted value is unchanged

function Tip({ active, payload }: { active?: boolean; payload?: { payload: TrendPoint }[] }) {
  const p = active ? payload?.[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rounded border border-slate-200 bg-white p-2 text-xs shadow">
      <p className="font-mono font-semibold">{p.shortId}</p>
      <p>{utc(p.startedAt)}</p>
      <p>pass rate {p.rateText}</p>
      <p className="text-slate-500">{p.groupLabel}</p>
      <p>{p.reasons.length ? `not on a trend line: ${p.reasons.join(", ")}` : "comparable full-suite run"}</p>
    </div>
  );
}

export function TrendChart() {
  const runs = useApi(fetchRunsForChart);
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
                  <span role="note" className="rounded bg-amber-50 px-2 py-0.5 text-amber-900">
                    Showing only the latest {CHART_RUN_LIMIT} of {total} runs.
                  </span>
                )}
              </div>

              {t.groups.length === 0 && (
                <p role="note" className="rounded border border-slate-200 bg-slate-50 p-2 text-sm">
                  No comparable full-suite runs yet (registered, full suite, complete), so there is no trend line. Every
                  run below is a separate marker. A complete, full-suite run that matches its registration would be the first
                  comparable full-suite baseline - whether a given run qualifies is known only after it has run.
                </p>
              )}
              {t.groups.some((g) => g.baseline) && (
                <p className="text-sm text-slate-600">
                  A group with one run shows a first comparable full-suite baseline, not a trend.
                </p>
              )}

              {allPoints.length > 0 && (
                <div className="overflow-x-auto" role="img" aria-label={summary}>
                  <ScatterChart width={760} height={280} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="x" domain={["dataMin", "dataMax"]} scale="time" name="started"
                           tickFormatter={(v: number) => utc(new Date(v).toISOString()).slice(5, 16)} tick={{ fontSize: 10 }} />
                    <YAxis type="number" dataKey="rate" domain={[0, 1]} tickFormatter={pct} name="pass rate" />
                    <Tooltip content={<Tip />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
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

              <details className="text-sm">
                <summary className="cursor-pointer text-slate-600">Data table ({allPoints.length} points{lines.length ? `, ${lines.length} line(s)` : ""})</summary>
                <table className="mt-2 w-full text-left text-xs" aria-label="pass rate over time (data)">
                  <thead className="uppercase text-slate-500">
                    <tr><th className="pr-2">Run</th><th className="pr-2">Started</th><th className="pr-2">Pass rate</th><th className="pr-2">Group</th><th>On a trend line?</th></tr>
                  </thead>
                  <tbody>
                    {allPoints.sort((a, b) => a.x - b.x).map((p) => (
                      <tr key={p.suiteId} className="border-t border-slate-100">
                        <td className="pr-2 font-mono">{p.shortId}</td><td className="pr-2">{utc(p.startedAt)}</td>
                        <td className="pr-2">{p.rateText}</td><td className="pr-2">{p.groupLabel}</td>
                        <td>{p.reasons.length ? `no - ${p.reasons.join(", ")}` : "yes"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
              {t.noValue.length > 0 && (
                <p className="text-xs text-slate-500">
                  Not plotted (no evaluated runs, so no pass rate - never shown as 0%): {t.noValue.map((s) => s.short_id).join(", ")}
                </p>
              )}
              {!includeScripted && t.hiddenScripted > 0 && (
                <p className="text-xs text-slate-500">{t.hiddenScripted} scripted run(s) hidden.</p>
              )}
            </div>
          );
        }}
      </Loaded>
    </Card>
  );
}

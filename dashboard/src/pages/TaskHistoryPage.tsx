// One task across every stored run (GET /tasks/{id}/history, paginated) and the exploratory before/after
// (GET /tasks/{id}/measure) with ALL of its limitations. Values are the server's; nothing is recalculated.
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from "recharts";
import { api, PAGE_SIZE, type Measure } from "../api/client";
import { useApi } from "../api/useApi";
import { historyBars, OUTCOME_COLOR } from "../charts/data";
import { Badge, Card, KindBadge, Loaded, OutcomeBadge } from "../components/ui";
import { num, short, utc } from "../format";

function MeasureTable({ m }: { m: Measure }) {
  if (m.groups.length === 0) return <p className="text-sm">No executed runs of this task yet.</p>;
  const cols: [string, (g: Measure["groups"][number]) => React.ReactNode][] = [
    ["Agent", (g) => <><KindBadge kind={g.kind} /> {g.model}</>],
    ["Tools", (g) => (g.tools === "unknown" ? "unknown (not recorded)" : `${g.tools.slice(0, 8)} (${g.calculator})`)],
    ["Suites / scheduled", (g) => `${g.suites} / ${g.scheduled}`],
    ["Correct (of evaluated)", (g) => `${g.passed} / ${g.evaluated}`],
    ["Infra errors (not counted)", (g) => (g.infra_errors.length ? `${g.infra_errors.length} (${[...new Set(g.infra_errors)].join(", ")})` : "0")],
    ["Skipped", (g) => g.skipped],
    ["Avg LLM calls", (g) => num(g.avg_llm_calls, 2)],
    ["Avg steps", (g) => num(g.avg_steps, 2)],
    ["Runs with round() errors", (g) => `${g.runs_with_round_errors} / ${g.evaluated} (${g.round_errors})`],
    ["Tool errors", (g) => g.tool_errors],
    ["Near step limit", (g) => `${g.near_step_limit} / ${g.evaluated}`],
    ["Step-limit failures", (g) => `${g.step_limit_failures} / ${g.evaluated}`],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm" aria-label="measure by agent and tools">
        <tbody>
          {cols.map(([label, cell]) => (
            <tr key={label} className="border-t border-border">
              <th className="py-1 pr-4 font-normal text-muted">{label}</th>
              {m.groups.map((g, i) => <td key={i} className="py-1 pr-4">{cell(g)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TaskHistoryPage() {
  const { taskId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const history = useApi(() => api.history(taskId, { offset }), [taskId, offset]);
  const measure = useApi(() => api.measure(taskId), [taskId]);
  const go = (o: number) => setParams(o > 0 ? { offset: String(o) } : {});

  return (
    <div className="space-y-4">
      <Link to="/runs" className="text-sm text-accent hover:underline">← all runs</Link>
      <h2 className="text-title">Task <span className="font-mono">{taskId}</span> across runs</h2>

      <Loaded state={history}>
        {({ items, pagination }) => {
          const bars = historyBars(items);
          const summary = `LLM calls per run, oldest first: ${bars.map((b) => `${b.label} ${b.outcome} ${b.llmCalls ?? "not run"}`).join("; ")}.`;
          return items.length === 0 ? (
            <p className="rounded border border-dashed border-border-strong bg-surface p-6 text-center text-muted">No stored runs of this task yet.</p>
          ) : (
            <>
              <Card title={`LLM calls per run (this page: ${items.length} of ${pagination.total})`}>
                <div className="overflow-x-auto" role="img" aria-label={summary}>
                  <BarChart width={Math.max(360, bars.length * 70)} height={220} data={bars}
                            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="llmCalls" name="LLM calls" isAnimationActive={false}>
                      {bars.map((b) => <Cell key={b.key} fill={OUTCOME_COLOR[b.outcome] ?? "rgb(var(--neutral-fg))"} />)}
                    </Bar>
                  </BarChart>
                </div>
                <p className="mt-1 text-[13px] text-muted">
                  Colour = outcome: <span className="text-success-fg">passed</span>, <span className="text-danger-fg">failed</span>,{" "}
                  <span className="text-warning-fg">infra error</span>; skipped runs have no bar. Each bar is a separate run (no line implied).
                </p>
              </Card>

              <Card title="History (newest first)">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm" aria-label="task history">
                    <thead className="text-[13px] uppercase text-muted">
                      <tr><th className="py-1 pr-3">Run</th><th className="pr-3">Started</th><th className="pr-3">Agent</th>
                        <th className="pr-3">Tools</th><th className="pr-3">Task ver.</th><th className="pr-3">Rep</th>
                        <th className="pr-3">Outcome</th><th className="pr-3">LLM calls</th><th>Answer / reason</th></tr>
                    </thead>
                    <tbody>
                      {items.map((h, i) => (
                        <tr key={`${h.suite_id}-${h.repeat}-${i}`} className="border-t border-border">
                          <td className="py-1 pr-3 font-mono">
                            <Link to={`/suites/${h.suite_id}`} className="text-accent hover:underline" title="run details (trace one click away)">{short(h.suite_id)}</Link>
                          </td>
                          <td className="pr-3 whitespace-nowrap">{utc(h.started_at)}</td>
                          <td className="pr-3"><KindBadge kind={h.provider === "fake" ? "scripted" : "real"} /> {h.model}</td>
                          <td className="pr-3 font-mono">{h.tools_fingerprint ? h.tools_fingerprint.slice(0, 8) : <span title="not recorded">unknown</span>}</td>
                          <td className="pr-3 font-mono">{h.task_hash ? h.task_hash.slice(0, 8) : "—"}</td>
                          <td className="pr-3">{h.repeat + 1}</td>
                          <td className="pr-3">{h.outcome === "skipped" ? <Badge color="slate">skipped</Badge> : <OutcomeBadge outcome={h.outcome} />}</td>
                          <td className="pr-3">{h.llm_calls ?? "—"}</td>
                          <td className="font-mono">{h.outcome === "skipped" ? h.reason : h.outcome === "infra_error" ? `(${h.error_kind})` : h.final_answer ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <nav className="mt-2 flex items-center justify-between text-sm" aria-label="history pages">
                  <span className="text-muted">{pagination.offset + 1}–{pagination.offset + pagination.returned} of {pagination.total}</span>
                  <span className="flex gap-2">
                    <button disabled={pagination.offset === 0} onClick={() => go(Math.max(0, offset - PAGE_SIZE))} className="rounded border px-3 py-1 disabled:opacity-40">Previous</button>
                    <button disabled={pagination.next_offset === null} onClick={() => pagination.next_offset !== null && go(pagination.next_offset)} className="rounded border px-3 py-1 disabled:opacity-40">Next</button>
                  </span>
                </nav>
              </Card>
            </>
          );
        }}
      </Loaded>

      <Card title="Exploratory before/after (grouped by agent and tools)">
        <Loaded state={measure}>
          {(m) => (
            <>
              <MeasureTable m={m} />
              <div role="note" className="mt-3 rounded border border-warning-fg/40 bg-warning-bg p-3 text-sm">
                <p className="font-semibold">Limitations - read before drawing conclusions:</p>
                <ul className="mt-1 list-disc pl-5">{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              </div>
            </>
          )}
        </Loaded>
      </Card>
    </div>
  );
}

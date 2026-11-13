// Failure analysis of one run (GET /suites/{id}/failures): categories with evidence, near misses, and
// infrastructure errors kept APART (they are not agent failures). Every number is the server's.
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { api, type RunAnalysis } from "../api/client";
import { useApi } from "../api/useApi";
import { categoryBars } from "../charts/data";
import { Badge, Card, Loaded } from "../components/ui";
import { short } from "../format";

function runLabel(r: RunAnalysis) {
  return `${r.task_id}${r.repeat > 0 ? ` #${r.repeat + 1}` : ""}`;
}

export function FailuresPage() {
  const { suiteId = "" } = useParams();
  const failures = useApi(() => api.failures(suiteId), [suiteId]);

  return (
    <div className="space-y-3">
      <Link to={`/suites/${suiteId}`} className="text-sm text-accent hover:underline">← run {short(suiteId)}</Link>
      <Loaded state={failures}>
        {({ note, analysis: a }) => {
          const runs = a.runs ?? [];
          const bars = categoryBars(a.category_counts);
          const infra = runs.filter((r) => r.outcome === "infra_error");
          const warned = runs.filter((r) => (r.warnings ?? []).length > 0);
          const summary = bars.length === 0
            ? "No agent failures in this run."
            : `Failure categories: ${bars.map((b) => `${b.category} ${b.runs}`).join(", ")}.`;
          return (
            <div className="space-y-4">
              <h2 className="text-title">Failure analysis · run {short(a.suite_id)}</h2>
              <p className="text-sm text-muted">{note}</p>

              <Card title="Summary (from the server)">
                <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div><dt className="text-muted">Failed (agent)</dt><dd className="text-lg font-semibold">{a.failed_runs}</dd></div>
                  <div><dt className="text-muted">Passed</dt><dd className="text-lg font-semibold">{a.passed_runs}</dd></div>
                  <div><dt className="text-muted">Infra errors (not failures)</dt><dd className="text-lg font-semibold">{a.infra_errors}</dd></div>
                  <div><dt className="text-muted">Skipped (never run)</dt><dd className="text-lg font-semibold">{a.skipped_runs}</dd></div>
                </dl>
                {a.retries_not_recorded > 0 && (
                  <p className="mt-2 text-[13px] text-muted">
                    Retries not recorded for {a.retries_not_recorded} run(s) (stored before retries were captured): unknown, not zero.
                  </p>
                )}
              </Card>

              <Card title="Failure categories">
                {bars.length === 0 ? (
                  <p className="text-sm">No agent failures in this run.</p>
                ) : (
                  <>
                    <div className="overflow-x-auto" role="img" aria-label={summary}>
                      <BarChart width={Math.max(360, bars.length * 120)} height={220} data={bars}
                                margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                        <YAxis allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="runs" name="failed runs" fill="rgb(var(--danger-fg))" isAnimationActive={false} />
                      </BarChart>
                    </div>
                    <table className="mt-2 w-full text-left text-sm" aria-label="failure categories (data)">
                      <thead className="text-[13px] uppercase text-muted"><tr><th>Category</th><th>Failed runs</th></tr></thead>
                      <tbody>
                        {bars.map((b) => <tr key={b.category} className="border-t border-border"><td className="font-mono">{b.category}</td><td>{b.runs}</td></tr>)}
                      </tbody>
                    </table>
                  </>
                )}
              </Card>

              {bars.map(({ category }) => (
                <Card key={category} title={category}>
                  <ul className="space-y-1 text-sm">
                    {runs.filter((r) => r.category === category).map((r) => (
                      <li key={r.run_id}>
                        <Link to={`/suites/${a.suite_id}/runs/${r.run_id}`} className="font-mono text-accent hover:underline">{runLabel(r)}</Link>
                        {" — "}{(r.signals ?? []).find((s) => s.name === category)?.evidence}
                      </li>
                    ))}
                  </ul>
                </Card>
              ))}

              <Card title="Infrastructure errors (NOT agent failures)">
                {infra.length === 0 ? <p className="text-sm">None.</p> : (
                  <ul className="space-y-1 text-sm">
                    {infra.map((r) => (
                      <li key={r.run_id}><span className="font-mono">{runLabel(r)}</span> <Badge color="amber">{r.infra_error_kind ?? "infra error"}</Badge></li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card title="Near misses (warnings only - they never change pass/fail)">
                {warned.length === 0 ? <p className="text-sm">None.</p> : (
                  <>
                    <p className="mb-2 text-sm">
                      {Object.entries(a.warning_counts ?? {}).map(([w, n]) => <span key={w} className="mr-2"><Badge color="amber">{w}</Badge> ×{n}</span>)}
                    </p>
                    <ul className="space-y-1 text-sm">
                      {warned.map((r) => (
                        <li key={r.run_id}>
                          <Link to={`/suites/${a.suite_id}/runs/${r.run_id}`} className="font-mono text-accent hover:underline">{runLabel(r)}</Link>
                          {" — "}{(r.warnings ?? []).map((w) => w.evidence).join("; ")}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </Card>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}

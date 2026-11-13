// Overview: the state of the benchmark at a glance - ONLY the API's own data.
//   * every number is a server value or a count the server reports (pagination totals, registrations);
//   * no averages across runs or suites (they are not comparable);
//   * a value that could not be loaded is "Not available" with the reason - never 0.
import { Link } from "react-router-dom";
import { ACTIVE_JOB_STATES, SUITES, api, fetchRunsForChart, type RegisteredSuite, type SuiteSummary } from "../api/client";
import { useApi, type ApiState } from "../api/useApi";
import { Card, MetricCard } from "../components/Card";
import { EmptyState, ProgressBar } from "../components/feedback";
import { DataTable } from "../components/Table";
import { TrendChart } from "../components/TrendChart";
import { Badge, CompleteBadge, KindBadge, Loaded, ScopeBadge } from "../components/ui";
import { utc } from "../format";

const why = (s: ApiState<unknown>) => s.status === "error" ? `Could not load (${s.error.code}).` : undefined;
const valueOf = <T, R>(s: ApiState<T>, pick: (d: T) => R): R | null => s.status === "ready" ? pick(s.data) : null;

/** The newest REAL run that covered its whole suite (as the server labels it). */
export function latestRealFullRun(items: SuiteSummary[]): SuiteSummary | undefined {
  return items.find((s) => s.kind === "real" && s.scope === "full");
}

function SuitesCard({ regs, runs }: { regs: ApiState<RegisteredSuite[]> & { reload: () => void }; runs: SuiteSummary[] | null }) {
  return (
    <Card title="Suites">
      <Loaded state={regs}>
        {(list) => {
          const registered = new Set(list.map((r) => r.suite));
          return (
            <ul className="flex flex-col gap-3" aria-label="suites">
              {list.map((r) => (
                <li key={r.suite} className="rounded-lg border border-border bg-surface-2 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{r.suite}</span>
                    <Badge color="green">registered v{r.version}</Badge></div>
                  <p className="mt-1 text-[13px] text-muted">
                    {r.tasks.length} tasks · suite <span className="font-mono">{r.suite_fingerprint}</span> · registered at git {r.git_head ? r.git_head.slice(0, 7) : "not recorded"}
                  </p>
                </li>
              ))}
              {SUITES.filter((name) => !registered.has(name)).map((name) => (
                <li key={name} className="rounded-lg border border-border bg-surface-2 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{name}</span>
                    <Badge color="slate">unregistered</Badge></div>
                  <p className="mt-1 text-[13px] text-muted">results are shown, but never joined into a trend line</p>
                </li>
              ))}
              {runs && runs.some((s) => s.tools_fingerprint === null) && (
                <li className="rounded-lg bg-accent-soft px-4 py-3 text-[13px]">
                  Tools not recorded for {runs.filter((s) => s.tools_fingerprint === null).map((s) => s.short_id).join(", ")}:
                  shown as unknown, never assumed equal to a known version.
                </li>
              )}
            </ul>
          );
        }}
      </Loaded>
    </Card>
  );
}

export function OverviewPage() {
  const all = useApi(() => api.suites({ limit: 1 }));
  const real = useApi(() => api.suites({ limit: 1, realOnly: true }));
  const regs = useApi(api.registrations);
  const jobs = useApi(api.jobs);
  const runs = useApi(fetchRunsForChart);

  const items = valueOf(runs, (d) => d.items);
  const latest = items ? latestRealFullRun(items) : undefined;
  const active = valueOf(jobs, (d) => d.items.find((j) => ACTIVE_JOB_STATES.includes(j.status)) ?? false);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-title">Overview</h1>
          <p className="mt-1 text-muted">Stored benchmark results from the local API. The dashboard shows the server's numbers and computes no metrics.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/runs" className="inline-flex h-10 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-semibold hover:bg-surface-2">All runs</Link>
          <Link to="/runs/new" className="inline-flex h-10 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent hover:bg-accent/90">Start a run</Link>
        </div>
      </div>

      <section aria-label="key figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Stored runs" value={valueOf(all, (d) => d.pagination.total)} unavailableReason={why(all)}
                    detail={real.status === "ready" ? `${real.data.pagination.total} real-LLM run(s) · server counts` : real.status === "error" ? "real-LLM count not available" : undefined} />
        <MetricCard label="Registered suites" value={valueOf(regs, (d) => d.length)} unavailableReason={why(regs)}
                    detail={regs.status === "ready" ? regs.data.map((r) => `${r.suite} v${r.version}`).join(", ") || "none registered yet" : undefined} />
        <MetricCard label="Latest real full-suite run"
                    value={runs.status === "ready" ? (latest ? latest.pass_rate.text.replace(/ \(.*\)$/, "") : null) : null}
                    suffix={latest?.pass_rate.text.match(/\(.*\)$/)?.[0]}
                    unavailableReason={runs.status === "error" ? why(runs) : runs.status === "ready" ? "No real full-suite run stored yet." : undefined}
                    detail={latest && (
                      <span className="flex flex-wrap items-center gap-1.5">
                        <Link to={`/suites/${latest.suite_id}`} className="font-mono font-semibold text-accent hover:underline">{latest.short_id}</Link>
                        <span>{latest.suite_name}</span><KindBadge kind={latest.kind} />
                        <ScopeBadge scope={latest.scope} registration={latest.registration_status} />
                        {!latest.complete && <CompleteBadge complete={false} />}
                      </span>)} />
        <MetricCard label="Active run"
                    value={active === null ? null : active === false ? "None" : `${active.completed_tasks}/${active.total_tasks}`}
                    unavailableReason={why(jobs)}
                    detail={active === false ? "no run in progress since this server started"
                      : active ? (
                        <span className="flex flex-col gap-1.5">
                          <Link to={`/jobs/${active.job_id}`} className="font-semibold text-accent hover:underline">{active.agent} on {active.suite} · follow it →</Link>
                          <ProgressBar percent={active.percent} label="active run progress" />
                        </span>) : undefined} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <TrendChart runs={runs} />
        <SuitesCard regs={regs} runs={items} />
      </div>

      <Card title="Recent runs" actions={<Link to="/runs" className="text-sm font-medium text-accent hover:underline">All runs →</Link>}>
        <Loaded state={runs}>
          {({ items: list }) => list.length === 0
            ? <EmptyState title="No runs stored yet">Start one from <Link to="/runs/new" className="text-accent underline">Start a run</Link>.</EmptyState>
            : (
              <DataTable<SuiteSummary>
                label="recent runs" rows={list.slice(0, 5)} rowKey={(s) => s.suite_id}
                columns={[
                  { key: "id", header: "Run", cell: (s) => <Link to={`/suites/${s.suite_id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{s.short_id}</Link> },
                  { key: "suite", header: "Suite", cell: (s) => s.suite_name },
                  { key: "agent", header: "Agent", cell: (s) => <span className="inline-flex items-center gap-2"><KindBadge kind={s.kind} /><span className="text-[13px] text-muted">{s.model}</span></span> },
                  { key: "scope", header: "Scope", cell: (s) => <ScopeBadge scope={s.scope} registration={s.registration_status} /> },
                  { key: "rate", header: "Pass rate", cell: (s) => <span className="tabular-nums">{s.pass_rate.text}</span> },
                  { key: "status", header: "Status", cell: (s) => <CompleteBadge complete={s.complete} /> },
                  { key: "started", header: "Started", cell: (s) => <span className="whitespace-nowrap tabular-nums">{utc(s.started_at)}</span> },
                ]}
              />
            )}
        </Loaded>
      </Card>
    </div>
  );
}

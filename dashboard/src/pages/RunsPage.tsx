// Every stored benchmark run, newest first. The table and the pass-rate chart share ONE load of the
// latest <= 500 runs (fetchRunsForChart). Filters and pages work on those loaded runs - the page says so.
// Filters live in the URL (?suite=shop-hard&kind=real&page=2), so the back button and bookmarks work.
// Values are shown exactly as the API sends them.
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CHART_RUN_LIMIT, fetchRunsForChart, type SuiteSummary } from "../api/client";
import { useApi } from "../api/useApi";
import { Button } from "../components/Button";
import { EmptyState } from "../components/feedback";
import { Select } from "../components/form";
import { TrendChart } from "../components/TrendChart";
import { CompleteBadge, KindBadge, Loaded, ScopeBadge } from "../components/ui";
import { utc } from "../format";

const MAX_COMPARE = 5;
export const RUNS_PAGE_SIZE = 20;

/** Why the Compare button is disabled (null = it may be pressed). The server still checks everything. */
export function compareBlocker(selected: Map<string, string>): string | null {
  if (selected.size < 2) return "select 2 to 5 runs to compare";
  if (selected.size > MAX_COMPARE) return `at most ${MAX_COMPARE} runs can be compared`;
  const suites = new Set(selected.values());
  if (suites.size > 1) return `runs of different suites cannot be compared (${[...suites].sort().join(", ")})`;
  return null;
}

export type RunFilters = { suite: string; kind: string; scope: string; status: string };

/** Keep only the runs matching every chosen filter ("all" = no filter). Display only: nothing is computed. */
export function filterRuns(items: SuiteSummary[], f: RunFilters): SuiteSummary[] {
  return items.filter((s) =>
    (f.suite === "all" || s.suite_name === f.suite) &&
    (f.kind === "all" || s.kind === f.kind) &&
    (f.scope === "all" || s.scope === f.scope) &&
    (f.status === "all" || (f.status === "complete" ? s.complete : !s.complete)));
}

function Segmented({ label, value, options, onChange }: {
  label: string; value: string; options: [string, string][]; onChange: (v: string) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex gap-0.5 rounded-lg border border-border bg-surface-2 p-[3px]">
      {options.map(([v, text]) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
                className={`rounded-md px-2.5 py-1 text-[13px] font-medium ${value === v ? "bg-surface text-fg shadow-[0_0_0_1px_rgb(var(--border-strong))]" : "text-muted hover:text-fg"}`}>
          {text}
        </button>
      ))}
    </div>
  );
}

export function RunsPage() {
  const runs = useApi(fetchRunsForChart);
  const [params, setParams] = useSearchParams();
  const filters: RunFilters = {
    suite: params.get("suite") ?? "all", kind: params.get("kind") ?? "all",
    scope: params.get("scope") ?? "all", status: params.get("status") ?? "all",
  };
  const pageNo = Math.max(1, Number(params.get("page")) || 1);
  const [selected, setSelected] = useState<Map<string, string>>(new Map()); // suite_id -> suite_name
  const navigate = useNavigate();
  const blocker = compareBlocker(selected);

  const set = (patch: Partial<RunFilters & { page: number }>) => {
    const next = { ...filters, page: 1, ...patch };
    const p = new URLSearchParams();
    for (const k of ["suite", "kind", "scope", "status"] as const) if (next[k] !== "all") p.set(k, next[k]);
    if (next.page > 1) p.set("page", String(next.page));
    setParams(p);
  };
  const toggle = (id: string, suiteName: string) =>
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(id)) next.delete(id);
      else next.set(id, suiteName);
      return next;
    });
  const compare = () => navigate(`/compare?${new URLSearchParams([...selected.keys()].map((id) => ["ids", id]))}`);

  const suiteNames = useMemo(
    () => runs.status === "ready" ? [...new Set(runs.data.items.map((s) => s.suite_name))].sort() : [],
    [runs]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-title">Runs</h1>
          <p className="mt-1 text-muted">Every stored benchmark run, newest first, exactly as the API reports it.</p>
        </div>
        <Link to="/runs/new" className="inline-flex h-10 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent hover:bg-accent/90">
          Start a run
        </Link>
      </div>

      <TrendChart runs={runs} />

      <section className="overflow-hidden rounded-card border border-border bg-surface shadow-card" aria-label="run list">
        <div className="flex flex-wrap items-center gap-3 px-5 py-4">
          <h2 className="mr-2 text-base font-semibold">All runs</h2>
          <label className="flex items-center gap-2 text-[13px]">
            <span className="text-muted">Suite</span>
            <Select aria-label="Suite" className="w-auto py-1.5" value={filters.suite} onChange={(e) => set({ suite: e.target.value })}>
              <option value="all">All suites</option>
              {suiteNames.map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </label>
          <Segmented label="Agent kind" value={filters.kind} onChange={(kind) => set({ kind })}
                     options={[["all", "All"], ["real", "Real LLM"], ["scripted", "Scripted"]]} />
          <Segmented label="Scope" value={filters.scope} onChange={(scope) => set({ scope })}
                     options={[["all", "Any scope"], ["full", "Full suite"], ["subset", "Subset"]]} />
          <Segmented label="Status" value={filters.status} onChange={(status) => set({ status })}
                     options={[["all", "Any status"], ["complete", "Complete"], ["incomplete", "Incomplete"]]} />
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-border px-5 py-3 text-sm">
          <Button variant="primary" size="sm" onClick={compare} disabled={blocker !== null}>Compare ({selected.size})</Button>
          <span className="text-muted" data-testid="compare-hint">{blocker ?? "ready to compare"}</span>
          {selected.size > 0 && <Button variant="ghost" size="sm" onClick={() => setSelected(new Map())}>clear selection</Button>}
        </div>

        <Loaded state={runs}>
          {({ items, total, capped }) => {
            const matching = filterRuns(items, filters);
            const pages = Math.max(1, Math.ceil(matching.length / RUNS_PAGE_SIZE));
            const current = Math.min(pageNo, pages);
            const shown = matching.slice((current - 1) * RUNS_PAGE_SIZE, current * RUNS_PAGE_SIZE);
            const first = matching.length ? (current - 1) * RUNS_PAGE_SIZE + 1 : 0;
            if (items.length === 0) {
              return <div className="p-5"><EmptyState title="No runs stored yet">Start one from <Link className="text-accent underline" to="/runs/new">Start a run</Link> or with python scripts/run_benchmark.py.</EmptyState></div>;
            }
            return (
              <>
                <p className="border-t border-border px-5 py-2 text-[13px] text-muted" data-testid="filter-scope">
                  Filters apply to the {items.length} run(s) loaded{capped ? ` (only the latest ${CHART_RUN_LIMIT} of ${total} stored)` : ` (all ${total} stored)`}.
                </p>
                {matching.length === 0 ? (
                  <div className="p-5"><EmptyState title="No runs match these filters." /></div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[980px] border-collapse text-left text-table" aria-label="runs">
                      <thead>
                        <tr className="bg-surface-2 text-xs font-semibold uppercase tracking-wider text-muted">
                          <th className="border-y border-border px-4 py-2.5"><span className="sr-only">select</span></th>
                          <th className="border-y border-border px-4 py-2.5">Run</th><th className="border-y border-border px-4 py-2.5">Started</th>
                          <th className="border-y border-border px-4 py-2.5">Agent</th><th className="border-y border-border px-4 py-2.5">Suite</th>
                          <th className="border-y border-border px-4 py-2.5">Scope</th>
                          <th className="border-y border-border px-4 py-2.5">Scheduled</th><th className="border-y border-border px-4 py-2.5">Pass rate</th>
                          <th className="border-y border-border px-4 py-2.5">Status</th><th className="border-y border-border px-4 py-2.5 text-right">Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shown.map((s) => (
                          <tr key={s.suite_id} className="border-b border-border hover:bg-surface-2/60">
                            <td className="px-4 py-3">
                              <input type="checkbox" aria-label={`select ${s.short_id} for comparison`}
                                     checked={selected.has(s.suite_id)} onChange={() => toggle(s.suite_id, s.suite_name)} />
                            </td>
                            <td className="px-4 py-3 font-mono text-[13px]">
                              <Link to={`/suites/${s.suite_id}`} className="font-semibold text-accent hover:underline">{s.short_id}</Link>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 tabular-nums">{utc(s.started_at)}</td>
                            <td className="px-4 py-3">
                              <div className="flex flex-col items-start gap-1"><KindBadge kind={s.kind} /><span className="text-[13px] text-muted">{s.model}</span></div>
                            </td>
                            <td className="px-4 py-3">{s.suite_name}</td>
                            <td className="px-4 py-3"><ScopeBadge scope={s.scope} registration={s.registration_status} />
                              {s.registration_status === "unregistered" && <span className="ml-1 text-[13px] text-muted">unregistered</span>}</td>
                            <td className="px-4 py-3">{s.scheduled_runs} run(s), ×{s.repeats}</td>
                            <td className="px-4 py-3 font-medium tabular-nums">{s.pass_rate.text}</td>
                            <td className="px-4 py-3">
                              <CompleteBadge complete={s.complete} />
                              {!s.complete && <span className="ml-1 text-[13px] text-muted">{s.infra_errors} infra, {s.skipped} skipped</span>}
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums">{s.total_llm_calls}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <nav className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm" aria-label="pages">
                  <span className="text-muted">{first}–{first + shown.length - (shown.length ? 1 : 0)} of {matching.length} matching</span>
                  <span className="flex gap-2">
                    <Button size="sm" disabled={current <= 1} onClick={() => set({ page: current - 1 })}>Previous</Button>
                    <Button size="sm" disabled={current >= pages} onClick={() => set({ page: current + 1 })}>Next</Button>
                  </span>
                </nav>
              </>
            );
          }}
        </Loaded>
      </section>
      <p className="text-[13px] text-muted">
        SCRIPTED = fixed answers written in advance to test the framework (not AI). SUBSET = only some of the suite's
        tasks ran, so its pass rate is not a full-suite score. INCOMPLETE = some runs were not executed or hit
        infrastructure errors (quota, budget, network); those are never counted as wrong answers.
      </p>
    </div>
  );
}

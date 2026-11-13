// Home page: every stored benchmark run, newest first. Pages and the "real only" filter live in the URL
// (?offset=20&real_only=true), so the back button and bookmarks work. Values shown exactly as the API sends them.
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, PAGE_SIZE } from "../api/client";
import { useApi } from "../api/useApi";
import { TrendChart } from "../components/TrendChart";
import { CompleteBadge, KindBadge, Loaded, ScopeBadge } from "../components/ui";

const MAX_COMPARE = 5;

/** Why the Compare button is disabled (null = it may be pressed). The server still checks everything. */
export function compareBlocker(selected: Map<string, string>): string | null {
  if (selected.size < 2) return "select 2 to 5 runs to compare";
  if (selected.size > MAX_COMPARE) return `at most ${MAX_COMPARE} runs can be compared`;
  const suites = new Set(selected.values());
  if (suites.size > 1) return `runs of different suites cannot be compared (${[...suites].sort().join(", ")})`;
  return null;
}
import { utc } from "../format";

export function RunsPage() {
  const [params, setParams] = useSearchParams();
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const realOnly = params.get("real_only") === "true";
  const page = useApi(() => api.suites({ offset, realOnly }), [offset, realOnly]);
  const [selected, setSelected] = useState<Map<string, string>>(new Map()); // suite_id -> suite_name
  const navigate = useNavigate();
  const blocker = compareBlocker(selected);
  const toggle = (id: string, suiteName: string) =>
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(id)) next.delete(id);
      else next.set(id, suiteName);
      return next;
    });
  const compare = () =>
    navigate(`/compare?${new URLSearchParams([...selected.keys()].map((id) => ["ids", id]))}`);

  const go = (next: { offset?: number; realOnly?: boolean }) => {
    const p = new URLSearchParams();
    const o = next.offset ?? offset;
    const r = next.realOnly ?? realOnly;
    if (o > 0) p.set("offset", String(o));
    if (r) p.set("real_only", "true");
    setParams(p);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Benchmark runs</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={realOnly} onChange={(e) => go({ offset: 0, realOnly: e.target.checked })} />
          Real LLM runs only
        </label>
      </div>

      <TrendChart />

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button onClick={compare} disabled={blocker !== null}
                className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-40">
          Compare ({selected.size})
        </button>
        <span className="text-slate-500" data-testid="compare-hint">{blocker ?? "ready to compare"}</span>
        {selected.size > 0 && (
          <button onClick={() => setSelected(new Map())} className="text-slate-600 underline">clear selection</button>
        )}
      </div>

      <Loaded state={page}>
        {({ items, pagination }) =>
          items.length === 0 ? (
            <p className="rounded border border-dashed border-slate-300 bg-white p-6 text-center text-slate-500">
              {realOnly ? "No real LLM runs stored yet." : "No runs stored yet. Start one: python scripts/run_benchmark.py"}
            </p>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-left text-sm" aria-label="runs">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2"><span className="sr-only">select</span></th>
                      <th className="px-3 py-2">Run</th><th className="px-3 py-2">Started</th>
                      <th className="px-3 py-2">Agent</th><th className="px-3 py-2">Suite</th>
                      <th className="px-3 py-2">Scope</th>
                      <th className="px-3 py-2">Scheduled</th><th className="px-3 py-2">Pass rate</th>
                      <th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">Requests</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((s) => (
                      <tr key={s.suite_id} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2">
                          <input type="checkbox" aria-label={`select ${s.short_id} for comparison`}
                                 checked={selected.has(s.suite_id)} onChange={() => toggle(s.suite_id, s.suite_name)} />
                        </td>
                        <td className="px-3 py-2 font-mono">
                          <Link to={`/suites/${s.suite_id}`} className="text-sky-700 hover:underline">{s.short_id}</Link>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">{utc(s.started_at)}</td>
                        <td className="px-3 py-2"><KindBadge kind={s.kind} /> <span className="ml-1">{s.model}</span></td>
                        <td className="px-3 py-2">{s.suite_name}</td>
                        <td className="px-3 py-2"><ScopeBadge scope={s.scope} registration={s.registration_status} /></td>
                        <td className="px-3 py-2">{s.scheduled_runs} run(s), ×{s.repeats}</td>
                        <td className="px-3 py-2 font-medium">{s.pass_rate.text}</td>
                        <td className="px-3 py-2">
                          <CompleteBadge complete={s.complete} />
                          {!s.complete && (
                            <span className="ml-1 text-xs text-slate-500">
                              {s.infra_errors} infra, {s.skipped} skipped
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">{s.total_llm_calls}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav className="flex items-center justify-between text-sm" aria-label="pages">
                <span className="text-slate-500">
                  {pagination.offset + 1}–{pagination.offset + pagination.returned} of {pagination.total}
                </span>
                <span className="flex gap-2">
                  <button disabled={pagination.offset === 0} onClick={() => go({ offset: Math.max(0, offset - PAGE_SIZE) })}
                          className="rounded border px-3 py-1 disabled:opacity-40">Previous</button>
                  <button disabled={pagination.next_offset === null}
                          onClick={() => pagination.next_offset !== null && go({ offset: pagination.next_offset })}
                          className="rounded border px-3 py-1 disabled:opacity-40">Next</button>
                </span>
              </nav>
            </>
          )
        }
      </Loaded>
      <p className="text-xs text-slate-500">
        SCRIPTED = fixed answers written in advance to test the framework (not AI). SUBSET = only some of the suite's
        tasks ran, so its pass rate is not a full-suite score. INCOMPLETE = some runs were not executed or hit
        infrastructure errors (quota, budget, network); those are never counted as wrong answers.
      </p>
    </div>
  );
}

// Compare 2-5 runs of one suite (GET /compare). The SERVER decides fairness and writes the conclusions;
// this page only displays them, with the metrics as the server's counts. Tables only (no chart).
import { Link, useSearchParams } from "react-router-dom";
import { api, type Compare } from "../api/client";
import { useApi } from "../api/useApi";
import { EmptyState } from "../components/feedback";
import { Badge, Card, Loaded, OutcomeBadge } from "../components/ui";
import { counts, num, short } from "../format";

function Fairness({ c }: { c: Compare }) {
  return c.fair ? (
    <div className="rounded border border-success-fg/30 bg-success-bg p-3 text-sm" data-testid="fairness">
      <Badge color="green">fair comparison</Badge> same tasks, grading, dataset and repeats (as checked by the server)
    </div>
  ) : (
    <div className="rounded border border-danger-fg/40 bg-danger-bg p-3 text-sm" data-testid="fairness">
      <Badge color="red">NOT A FAIR COMPARISON</Badge> these differ: {c.unfair_dimensions.join(", ")}
    </div>
  );
}

function CompareView({ c }: { c: Compare }) {
  const runs = c.suite_ids;
  const metricRows: [string, (i: number) => string][] = [
    ["Passed / evaluated", (i) => counts(c.metrics[i]?.pass_rate)],
    ["Avg steps", (i) => num(c.metrics[i]?.avg_steps)],
    ["Avg LLM calls", (i) => num(c.metrics[i]?.avg_llm_calls)],
    ["Avg tokens in", (i) => num(c.metrics[i]?.avg_input_tokens, 0)],
    ["LLM requests", (i) => String(c.metrics[i]?.total_llm_calls ?? "n/a")],
    ["Tool errors", (i) => String(c.metrics[i]?.tool_errors ?? "n/a")],
    ["Infra errors (not failures)", (i) => String(c.metrics[i]?.infra_errors ?? "n/a")],
    ["Complete", (i) => (c.metrics[i]?.complete ? "yes" : "NO")],
  ];
  const head = (
    <tr><th className="py-1 pr-4" />{runs.map((id) => (
      <th key={id} className="pr-4 font-mono"><Link to={`/suites/${id}`} className="text-accent hover:underline">{short(id)}</Link></th>
    ))}</tr>
  );
  return (
    <div className="space-y-4">
      <h2 className="text-title">Compare {runs.length} runs</h2>
      <Fairness c={c} />
      <p className="text-sm">
        Tools: <strong>{c.tools_status}</strong>
        {c.tools_status === "unknown" && " - not recorded for at least one run, so they are NOT assumed to be the same"}
        {" · "}Changed configuration dimensions: <strong>{c.changed_dimensions.length ? c.changed_dimensions.join(", ") : "none"}</strong>
      </p>

      <Card title="Conclusions (written by the server)">
        <ul className="list-disc space-y-1 pl-5 text-sm" aria-label="conclusions">
          {c.conclusions.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </Card>

      <Card title="Configuration and fairness dimensions">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" aria-label="dimensions">
            <thead className="text-[13px] uppercase text-muted">{head}</thead>
            <tbody>
              {Object.entries(c.dimensions).map(([label, values]) => {
                const differs = new Set(values).size > 1;                   // display highlight only
                return (
                  <tr key={label} className={`border-t border-border ${differs ? "bg-warning-bg" : ""}`} data-differs={differs}>
                    <th className="py-1 pr-4 font-normal text-muted">{label}</th>
                    {values.map((v, i) => <td key={i} className="pr-4 font-mono">{v === "not recorded" ? <em>not recorded</em> : v}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Results (the server's counts)">
        <table className="w-full text-left text-sm" aria-label="metrics">
          <thead className="text-[13px] uppercase text-muted">{head}</thead>
          <tbody>
            {metricRows.map(([label, cell]) => (
              <tr key={label} className="border-t border-border">
                <th className="py-1 pr-4 font-normal text-muted">{label}</th>
                {runs.map((id, i) => <td key={id} className="pr-4">{cell(i)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Per task (first repeat of each run)">
        <table className="w-full text-left text-sm" aria-label="per task">
          <thead className="text-[13px] uppercase text-muted">{head}</thead>
          <tbody>
            {c.tasks.map((t) => (
              <tr key={t.task_id} className={`border-t border-border ${t.differs ? "bg-warning-bg" : ""}`}>
                <th className="py-1 pr-4 font-mono font-normal">
                  {t.task_id}{t.differs && <span className="ml-1 text-[13px] text-warning-fg">differs</span>}
                </th>
                {t.outcomes.map((o, i) => <td key={i} className="pr-4">{o === "skipped" ? <Badge color="slate">skipped</Badge> : <OutcomeBadge outcome={o} />}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

export function ComparePage() {
  const [params] = useSearchParams();
  const ids = params.getAll("ids");
  const key = ids.join(",");
  // Opened from the sidebar with nothing selected: explain how to choose runs (no request is sent).
  const compare = useApi(() => (ids.length ? api.compare(ids) : Promise.resolve(null)), [key]);
  return (
    <div className="flex flex-col gap-4">
      <Link to="/runs" className="text-sm font-medium text-accent hover:underline">← all runs</Link>
      {ids.length === 0 ? (
        <>
          <h1 className="text-title">Compare runs</h1>
          <EmptyState title="Choose 2 to 5 runs of one suite"
                      action={<Link to="/runs" className="inline-flex h-10 items-center rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent">Go to Runs</Link>}>
            Tick runs in the Runs table and press Compare. The server checks whether the comparison is fair and
            writes the conclusions; this page shows them word for word.
          </EmptyState>
        </>
      ) : (
        <Loaded state={compare}>{(c) => (c ? <CompareView c={c} /> : null)}</Loaded>
      )}
    </div>
  );
}

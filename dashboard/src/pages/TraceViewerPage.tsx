// One task run, step by step (GET /suites/{id}/runs/{run_id}): every LLM turn, every tool call with its
// output or error, every evaluation check, and the rule-based failure analysis with its evidence.
import { Link, useParams } from "react-router-dom";
import { api, type RunDetail, type Signal } from "../api/client";
import { useApi } from "../api/useApi";
import { Badge, Card, Loaded, OutcomeBadge } from "../components/ui";
import { num, short, utc } from "../format";

function Signals({ title, items, tone }: { title: string; items: Signal[]; tone: "red" | "amber" }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2">
      <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <ul className="mt-1 space-y-1 text-sm">
        {items.map((s) => (
          <li key={`${s.name}-${s.evidence}`}>
            <Badge color={tone}>{s.name}</Badge> <span>{s.evidence}</span>
            {(s.step_indexes ?? []).length > 0 && (
              <span className="text-xs text-slate-500"> (step {(s.step_indexes ?? []).join(", ")})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Analysis({ detail }: { detail: RunDetail }) {
  const a = detail.analysis;
  if (!a) return <p className="text-sm text-slate-500">No failure analysis: this run stored no task definitions.</p>;
  if (detail.record.outcome === "infra_error") {
    return <p className="text-sm">Infrastructure error ({a.infra_error_kind}): not an agent failure, so not analysed.</p>;
  }
  // Lists with a default on the backend are optional in the contract: treat a missing list as empty.
  const signals = a.signals ?? [];
  const primary = signals.find((s) => s.name === a.category);
  return (
    <div>
      <p className="text-xs text-slate-500">Rule-based, from the stored trace: likely patterns, not the model's reasoning.</p>
      {a.category ? (
        <p className="mt-2"><Badge color="red">{a.category}</Badge> <span className="text-sm">{primary?.evidence}</span></p>
      ) : (
        <p className="mt-2 text-sm">No failure category (the run passed).</p>
      )}
      <Signals title="Additional signals" items={signals.filter((s) => s.name !== a.category)} tone="red" />
      <Signals title="Near misses (warnings only - never change pass/fail)" items={a.warnings ?? []} tone="amber" />
      {!a.retries_recorded && <p className="mt-2 text-xs text-slate-500">Retries: not recorded for this run (unknown, not zero).</p>}
    </div>
  );
}

function Trace({ d }: { d: RunDetail }) {
  const { run, evaluation } = d.record;
  const steps = run.trace.steps ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold font-mono">
          <Link to={`/tasks/${d.record.task_id}`} className="hover:underline" title="this task across all runs">{d.record.task_id}</Link>
          {d.record.repeat > 0 && ` #${d.record.repeat + 1}`}
        </h2>
        <OutcomeBadge outcome={d.record.outcome} />
        <span className="text-sm text-slate-500">run {short(run.run_id ?? "")} · status {run.status}</span>
      </div>
      <Card title="Summary">
        <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div><dt className="text-slate-500">Final answer</dt><dd className="font-mono">{run.final_answer ?? "—"}</dd></div>
          <div><dt className="text-slate-500">Steps / LLM calls</dt><dd>{steps.length} / {run.llm_calls}</dd></div>
          <div><dt className="text-slate-500">Duration</dt><dd>{num(run.duration_seconds)} s</dd></div>
          <div><dt className="text-slate-500">Retries</dt>
            <dd>{run.retries === null || run.retries === undefined ? "not recorded" : run.retries.length}</dd></div>
        </dl>
        {run.error && <p className="mt-2 text-sm text-red-800">Error ({run.error_kind}): {run.error}</p>}
      </Card>

      <Card title="Failure analysis"><Analysis detail={d} /></Card>

      {evaluation && (
        <Card title="Evaluation checks">
          <ul className="space-y-1 text-sm">
            {evaluation.checks.map((c) => (
              <li key={c.name}>
                <Badge color={c.passed ? "green" : "red"}>{c.passed ? "pass" : "fail"}</Badge>{" "}
                <span className="font-mono">{c.name}</span> — {c.reason}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={`Trace (${steps.length} steps)`}>
        <ol className="space-y-3">
          {steps.map((step) => {
            const call = step.tool_call;
            const args = call?.arguments ?? {};
            const query = typeof args["query"] === "string" ? (args["query"] as string) : null;
            return (
              <li key={step.index} className="rounded border border-slate-100 p-3" data-testid={`step-${step.index}`}>
                <p className="text-xs text-slate-500">
                  Step {step.index} · {utc(step.timestamp)}
                  {step.input_tokens !== null && ` · tokens ${step.input_tokens} in / ${step.output_tokens ?? "?"} out`}
                </p>
                {step.llm_output && <p className="mt-1 whitespace-pre-wrap text-sm">{step.llm_output}</p>}
                {call ? (
                  <div className="mt-2 text-sm">
                    <p><span className="font-semibold">Tool:</span> <span className="font-mono">{call.tool_name}</span></p>
                    {query !== null
                      ? <pre className="mt-1 overflow-x-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{query}</pre>
                      : <pre className="mt-1 overflow-x-auto rounded bg-slate-100 p-2 text-xs">{JSON.stringify(args)}</pre>}
                    {call.error !== null && call.error !== undefined ? (
                      <pre role="note" className="mt-1 whitespace-pre-wrap rounded bg-red-50 p-2 text-xs text-red-800">Error: {call.error}</pre>
                    ) : (
                      <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-emerald-50 p-2 text-xs">{call.output}</pre>
                    )}
                  </div>
                ) : (
                  !step.llm_output && <p className="mt-1 text-sm text-slate-500">(final answer step)</p>
                )}
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}

export function TraceViewerPage() {
  const { suiteId = "", runId = "" } = useParams();
  const detail = useApi(() => api.run(suiteId, runId), [suiteId, runId]);
  return (
    <div className="space-y-3">
      <Link to={`/suites/${suiteId}`} className="text-sm text-sky-700 hover:underline">← run {short(suiteId)}</Link>
      <Loaded state={detail}>{(d) => <Trace d={d} />}</Loaded>
    </div>
  );
}

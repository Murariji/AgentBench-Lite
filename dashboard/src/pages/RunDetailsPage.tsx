// One benchmark run (GET /suites/{id}): who ran, the registration check, the metrics and every task run.
// All numbers come from the server; pass rates are shown as the server's counts (no % computed here).
import { Link, useParams } from "react-router-dom";
import { api, type SuiteDetail } from "../api/client";
import { useApi } from "../api/useApi";
import { Badge, Card, CompleteBadge, KindBadge, Loaded, OutcomeBadge } from "../components/ui";
import { counts, num, short, utc } from "../format";

const REGISTRATION_TONE: Record<string, "green" | "amber" | "red" | "slate"> = {
  matches: "green", subset: "amber", differs: "red", unregistered: "slate", unknown: "slate",
};

function RegistrationBanner({ registration }: { registration: SuiteDetail["registration"] }) {
  const color = REGISTRATION_TONE[registration.status] ?? "slate";
  const box = { green: "border-emerald-200 bg-emerald-50", amber: "border-amber-300 bg-amber-50",
                red: "border-red-300 bg-red-50", slate: "border-slate-200 bg-slate-50" }[color];
  return (
    <div className={`rounded border p-3 text-sm ${box}`} data-testid="registration">
      <Badge color={color}>registration: {registration.status}</Badge>
      <p className="mt-1">{registration.line}</p>
      {registration.problems.map((p) => <p key={p} className="mt-1 text-red-800">• {p}</p>)}
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-slate-100 p-3">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function Details({ s }: { s: SuiteDetail }) {
  const m = s.metrics;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{s.suite_name} · run {short(s.suite_id)}</h2>
        <KindBadge kind={s.kind} />
        <CompleteBadge complete={s.complete} />
      </div>
      {s.kind !== "real" && (
        <p className="text-sm text-slate-600">
          SCRIPTED agent: fixed answers written in advance. This run tests the framework and says nothing about AI ability.
        </p>
      )}
      <RegistrationBanner registration={s.registration} />
      {!s.complete && (
        <div role="note" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
          Incomplete: {m.infra_errors} infrastructure error(s) and {m.skipped_runs} skipped run(s) are NOT counted as
          wrong answers. {s.stop_reason && <>Stopped: <strong>{s.stop_reason}</strong>.</>}
        </div>
      )}

      <Card title="Results (as computed by the server)">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="Passed / evaluated" value={counts(m.pass_rate)} hint={`${m.scheduled_runs} scheduled`} />
          {Object.entries(m.by_difficulty).map(([level, rate]) => (
            <Metric key={level} label={level} value={counts(rate)} />
          ))}
          {m.pass_at_k && <Metric label={`pass@${m.k}`} value={counts(m.pass_at_k)} hint="solved at least once" />}
          {m.pass_pow_k && <Metric label={`pass^${m.k}`} value={counts(m.pass_pow_k)} hint="solved every time" />}
          <Metric label="Avg steps" value={num(m.avg_steps)} />
          <Metric label="Avg LLM calls" value={num(m.avg_llm_calls)} />
          <Metric label="Avg tokens in / out" value={`${num(m.avg_input_tokens, 0)} / ${num(m.avg_output_tokens, 0)}`} />
          <Metric label="LLM requests" value={String(m.total_llm_calls)}
                  hint={s.request_budget !== null ? `budget ${s.request_budget}` : undefined} />
          <Metric label="Tool errors" value={`${m.tool_errors} of ${m.tool_calls} calls`} />
        </div>
      </Card>

      <Card title="Configuration">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <div><dt className="inline text-slate-500">Model: </dt><dd className="inline">{s.config.provider} / {s.config.model}</dd></div>
          <div><dt className="inline text-slate-500">Started: </dt><dd className="inline">{utc(s.started_at)}</dd></div>
          <div><dt className="inline text-slate-500">Config fingerprint: </dt><dd className="inline font-mono">{s.config_fingerprint}</dd></div>
          <div><dt className="inline text-slate-500">Tasks fingerprint: </dt><dd className="inline font-mono">{s.tasks_fingerprint ?? "n/a"}</dd></div>
          <div><dt className="inline text-slate-500">Dataset: </dt><dd className="inline font-mono">{s.dataset ?? "n/a"}</dd></div>
          <div>
            <dt className="inline text-slate-500">Tools: </dt>
            <dd className="inline">
              {s.tools === null ? "not recorded (run stored before tool versions existed)"
                : s.tools.map((t) => `${t.name} v${t.version}`).join(", ")}
            </dd>
          </div>
        </dl>
      </Card>

      <Card title={`Task runs (${s.runs.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr><th className="py-1 pr-3">Task</th><th className="pr-3">Level</th><th className="pr-3">Outcome</th>
                <th className="pr-3">Answer</th><th className="pr-3">Steps</th><th className="pr-3">LLM calls</th>
                <th className="pr-3">Retries</th><th className="pr-3">Failed checks</th><th /></tr>
            </thead>
            <tbody>
              {s.runs.map((r) => (
                <tr key={r.run_id} className="border-t border-slate-100">
                  <td className="py-1 pr-3 font-mono">{r.task_id}{s.repeats > 1 && ` #${r.repeat + 1}`}</td>
                  <td className="pr-3">{r.difficulty ?? "—"}</td>
                  <td className="pr-3"><OutcomeBadge outcome={r.outcome} />{r.error_kind && <span className="ml-1 text-xs text-slate-500">{r.error_kind}</span>}</td>
                  <td className="pr-3 font-mono">{r.final_answer ?? "—"}</td>
                  <td className="pr-3">{r.steps}</td>
                  <td className="pr-3">{r.llm_calls}</td>
                  <td className="pr-3">{r.retries === null ? <span title="unknown, not zero">not recorded</span> : r.retries}</td>
                  <td className="pr-3 text-red-800">{r.failed_checks.join(", ") || "—"}</td>
                  <td><Link to={`/suites/${s.suite_id}/runs/${r.run_id}`} className="text-sky-700 hover:underline">trace →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {s.skipped.length > 0 && (
          <p className="mt-2 text-sm text-slate-600">
            Skipped (never run): {s.skipped.map((k) => `${k.task_id}${s.repeats > 1 ? ` #${k.repeat + 1}` : ""}`).join(", ")}
            {" "}— {s.skipped[0]?.reason}
          </p>
        )}
      </Card>
    </div>
  );
}

export function RunDetailsPage() {
  const { suiteId = "" } = useParams();
  const suite = useApi(() => api.suite(suiteId), [suiteId]);
  return (
    <div className="space-y-3">
      <Link to="/" className="text-sm text-sky-700 hover:underline">← all runs</Link>
      <Loaded state={suite}>{(s) => <Details s={s} />}</Loaded>
    </div>
  );
}

// Step 10.4: start a benchmark run from the dashboard - REAL Gemini or a SCRIPTED test agent.
// Flow: fill the form -> "Estimate" (POST /estimates: the server says what it would cost and whether it would
// accept it) -> "Start" (POST /runs) -> the job page follows the progress.
// The dashboard decides NOTHING about safety: every gate (--allow-real-runs, confirm, budget, registration)
// is checked by the server, and the page only shows the server's answer. The API key never reaches the browser.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, SUITES, api, type Estimate, type RunRequest } from "../api/client";
import { useApi } from "../api/useApi";
import { Badge, Card, KindBadge } from "../components/ui";

type Agent = RunRequest["agent"];
type Form = { agent: Agent; suite: string; tasks: string; repeats: string; budget: string; confirm: boolean };

const AGENTS: { value: Agent; label: string }[] = [
  { value: "gemini", label: "Gemini (REAL LLM)" },
  { value: "careful", label: "careful (SCRIPTED test agent, not AI)" },
  { value: "sloppy", label: "sloppy (SCRIPTED test agent that falls into traps)" },
];

const SERVE_REAL = "python scripts/serve_api.py --allow-real-runs";

/** The form, turned into exactly the request the server receives (no defaults are invented here). */
export function toRequest(f: Form): RunRequest {
  const real = f.agent === "gemini";
  const tasks = f.tasks.split(/[\s,]+/).filter(Boolean);
  const budget = Number.parseInt(f.budget, 10);
  return {
    agent: f.agent, suite: f.suite, repeats: Number(f.repeats),
    ...(tasks.length ? { tasks } : {}),
    ...(real && Number.isFinite(budget) ? { budget } : {}),
    confirm: real && f.confirm,
  };
}

type Pending<T> = { status: "idle" } | { status: "loading" } | { status: "error"; error: ApiError } | { status: "ready"; data: T };
const asApiError = (e: unknown) => e instanceof ApiError ? e : new ApiError(0, "client_error", String(e));

function ErrorBox({ error, children }: { error: ApiError; children?: React.ReactNode }) {
  return (
    <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <p className="font-semibold">The server said no ({error.code})</p>
      <p className="mt-1">{error.message}</p>
      {children}
    </div>
  );
}

function EstimatePanel({ e }: { e: Estimate }) {
  const est = e.estimate as Record<string, unknown> | null;
  return (
    <Card title="Estimate (nothing was sent to any model)">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm" aria-label="estimate">
        <dt className="text-slate-500">agent</dt><dd>{e.agent} <KindBadge kind={e.kind} /></dd>
        <dt className="text-slate-500">suite</dt><dd>{e.suite}</dd>
        <dt className="text-slate-500">tasks</dt><dd>{e.tasks.length} ({e.tasks.join(", ")})</dd>
        <dt className="text-slate-500">runs</dt><dd>{e.runs} (tasks × repeats)</dd>
        {est && <>
          <dt className="text-slate-500">requests to Gemini</dt>
          <dd>typical {String(est.typical_requests)}, worst case {String(est.worst_case_requests)}</dd>
          <dt className="text-slate-500">budget (hard cap)</dt><dd>{String(est.budget ?? "not set")}</dd>
          <dt className="text-slate-500">time</dt><dd>about {String(est.estimated_seconds)} s</dd>
        </>}
        <dt className="text-slate-500">registration</dt><dd>{e.registration.line}</dd>
      </dl>
      {e.allowed
        ? <p data-testid="verdict" className="mt-3 rounded bg-emerald-50 p-2 text-sm text-emerald-800">The server would accept this run.</p>
        : (
          <div data-testid="verdict" className="mt-3 rounded bg-red-50 p-2 text-sm text-red-800">
            <p className="font-semibold">The server would NOT start this run:</p>
            <ul className="ml-5 list-disc">{e.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
      <p className="mt-2 text-xs text-slate-500">{e.note}</p>
    </Card>
  );
}

export function StartRunPage() {
  const health = useApi(api.health);
  const navigate = useNavigate();
  const [form, setForm] = useState<Form>({ agent: "gemini", suite: "shop-hard", tasks: "", repeats: "1", budget: "", confirm: false });
  const [estimate, setEstimate] = useState<Pending<Estimate>>({ status: "idle" });
  const [estimatedFor, setEstimatedFor] = useState<string | null>(null);
  const [start, setStart] = useState<Pending<null>>({ status: "idle" });

  const request = toRequest(form);
  const key = JSON.stringify(request);
  const real = form.agent === "gemini";
  const stale = estimatedFor !== null && estimatedFor !== key;      // the form changed after the estimate
  const realDisabled = health.status === "ready" && !health.data.real_runs_enabled;
  const canStart = estimate.status === "ready" && estimate.data.allowed && !stale && start.status !== "loading";

  const set = (patch: Partial<Form>) => { setForm((f) => ({ ...f, ...patch })); setStart({ status: "idle" }); };

  async function runEstimate() {
    setEstimate({ status: "loading" });
    setEstimatedFor(key);
    try {
      setEstimate({ status: "ready", data: await api.estimate(request) });
    } catch (e) {
      setEstimate({ status: "error", error: asApiError(e) });
    }
  }

  async function runStart() {
    setStart({ status: "loading" });
    try {
      const job = await api.startRun(request);
      navigate(`/jobs/${job.job_id}`);
    } catch (e) {
      setStart({ status: "error", error: asApiError(e) });
    }
  }

  const activeJob = start.status === "error" && start.error.code === "run_in_progress"
    ? (start.error.details as { active_job_id?: string } | null)?.active_job_id : undefined;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Start a run</h2>
      <p className="text-sm text-slate-600">
        Estimate first, then start. Every safety check happens on the server; this page shows its answer.
        Your Gemini API key stays on the server and never reaches the browser.
      </p>

      {health.status === "error" && <ErrorBox error={health.error} />}
      {real && realDisabled && (
        <div data-testid="real-disabled" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">Real Gemini runs are switched off on this server.</p>
          <p className="mt-1">To enable them, stop the API and start it again with:</p>
          <code className="mt-1 block rounded bg-white px-2 py-1">{SERVE_REAL}</code>
          <p className="mt-1">Each real run still needs your confirmation, a budget and a passing registration check.</p>
        </div>
      )}
      {real && health.status === "ready" && health.data.real_runs_enabled && (
        <p className="text-sm"><Badge color="blue">REAL runs enabled</Badge> on this server - a started run uses your free-tier quota.</p>
      )}

      <Card title="Run">
        <form className="grid gap-3 text-sm sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void runEstimate(); }}>
          <label className="flex flex-col gap-1">Agent
            <select className="rounded border p-1" value={form.agent} onChange={(e) => set({ agent: e.target.value as Agent })}>
              {AGENTS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">Suite
            <select className="rounded border p-1" value={form.suite} onChange={(e) => set({ suite: e.target.value })}>
              {SUITES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">Tasks (optional, comma-separated; empty = the whole suite)
            <input className="rounded border p-1" value={form.tasks} placeholder="e.g. hard-001, hard-007"
                   onChange={(e) => set({ tasks: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">Repeats (1-10)
            <input className="rounded border p-1" type="number" min={1} max={10} value={form.repeats}
                   onChange={(e) => set({ repeats: e.target.value })} />
          </label>
          {real && <>
            <label className="flex flex-col gap-1">Budget (hard cap on Gemini requests)
              <input className="rounded border p-1" type="number" min={1} value={form.budget} placeholder="e.g. 100"
                     onChange={(e) => set({ budget: e.target.value })} />
            </label>
            <label className="flex items-center gap-2 self-end">
              <input type="checkbox" checked={form.confirm} onChange={(e) => set({ confirm: e.target.checked })} />
              I confirm: send real requests to Gemini (uses my free-tier quota)
            </label>
          </>}
          {request.tasks && (
            <p className="text-amber-800 sm:col-span-2">
              A subset of tasks is not a full-suite score: it will be shown as a separate marker, never on a trend line.
            </p>
          )}
          <div className="flex gap-2 sm:col-span-2">
            <button type="submit" className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50"
                    disabled={estimate.status === "loading"}>
              Estimate
            </button>
            <button type="button" onClick={() => void runStart()} disabled={!canStart}
                    className="rounded bg-sky-700 px-3 py-1 text-white disabled:opacity-50">
              {real ? "Start REAL run" : "Start scripted run"}
            </button>
          </div>
          {stale && <p data-testid="stale" className="text-slate-600 sm:col-span-2">The form changed - estimate again before starting.</p>}
        </form>
      </Card>

      {estimate.status === "loading" && <p role="status">Asking the server…</p>}
      {estimate.status === "error" && <ErrorBox error={estimate.error} />}
      {estimate.status === "ready" && !stale && <EstimatePanel e={estimate.data} />}

      {start.status === "loading" && <p role="status">Starting…</p>}
      {start.status === "error" && (
        <ErrorBox error={start.error}>
          {activeJob && <Link to={`/jobs/${activeJob}`} className="mt-2 inline-block text-sky-700 underline">Follow the run in progress</Link>}
        </ErrorBox>
      )}
    </div>
  );
}

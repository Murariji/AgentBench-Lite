// Start a benchmark run - REAL Gemini or a SCRIPTED test agent - as a guided workflow:
//   1 Configure -> 2 Estimate (POST /estimates: what it would cost, and whether the server would accept it)
//   -> 3 Confirm & start (POST /runs) -> 4 Running -> 5 Results (the job page).
// The dashboard decides NOTHING about safety: every gate (--allow-real-runs, confirm, budget, registration)
// is checked by the server, and the page only shows the server's answer. Ticking the confirmation asks the
// server AGAIN, so "Start" is only possible after the server said yes to exactly that request.
// The API key never reaches the browser.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, SUITES, api, type Estimate, type RunRequest } from "../api/client";
import { useApi } from "../api/useApi";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Alert, Skeleton } from "../components/feedback";
import { Checkbox, Field, Input, Select } from "../components/form";
import { Stepper } from "../components/Stepper";
import { Badge, KindBadge } from "../components/ui";

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

function ServerNo({ error, children }: { error: ApiError; children?: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-lg border border-danger-fg/30 bg-danger-bg p-4 text-sm text-danger-fg">
      <p className="font-semibold">The server said no ({error.code})</p>
      <p className="mt-1">{error.message}</p>
      {children}
    </div>
  );
}

function EstimatePanel({ e }: { e: Estimate }) {
  const est = e.estimate as Record<string, unknown> | null;
  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm" aria-label="estimate">
        <dt className="text-muted">agent</dt><dd className="flex items-center gap-2">{e.agent} <KindBadge kind={e.kind} /></dd>
        <dt className="text-muted">suite</dt><dd>{e.suite}</dd>
        <dt className="text-muted">tasks</dt><dd>{e.tasks.length} ({e.tasks.join(", ")})</dd>
        <dt className="text-muted">runs</dt><dd>{e.runs} (tasks × repeats)</dd>
        {est && <>
          <dt className="text-muted">requests to Gemini</dt>
          <dd className="tabular-nums">typical {String(est.typical_requests)}, worst case {String(est.worst_case_requests)}</dd>
          <dt className="text-muted">budget (hard cap)</dt><dd className="tabular-nums">{String(est.budget ?? "not set")}</dd>
          <dt className="text-muted">time</dt><dd className="tabular-nums">about {String(est.estimated_seconds)} s</dd>
        </>}
        <dt className="text-muted">registration</dt><dd>{e.registration.line}</dd>
      </dl>
      {e.allowed
        ? <div data-testid="verdict" className="rounded-lg bg-success-bg px-4 py-3 text-sm font-medium text-success-fg">The server would accept this run.</div>
        : (
          <div data-testid="verdict" className="rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger-fg">
            <p className="font-semibold">The server would NOT start this run:</p>
            <ul className="ml-5 list-disc">{e.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        )}
      <p className="text-[13px] text-muted">{e.note}</p>
    </div>
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
  const fresh = estimate.status === "ready" && !stale;
  const canStart = fresh && estimate.status === "ready" && estimate.data.allowed && start.status !== "loading";
  const step = !fresh ? 0 : 2;                                        // 0 Configure, 2 Confirm & start

  const set = (patch: Partial<Form>) => { setForm((f) => ({ ...f, ...patch })); setStart({ status: "idle" }); };

  async function runEstimate(body: RunRequest = request) {
    setEstimate({ status: "loading" });
    setEstimatedFor(JSON.stringify(body));
    try {
      setEstimate({ status: "ready", data: await api.estimate(body) });
    } catch (e) {
      setEstimate({ status: "error", error: asApiError(e) });
    }
  }

  /** Ticking (or unticking) the confirmation changes the request, so the server is asked again. */
  function confirm(checked: boolean) {
    const next = { ...form, confirm: checked };
    setForm(next);
    setStart({ status: "idle" });
    void runEstimate(toRequest(next));
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
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-title">Start a run</h1>
        <p className="mt-1 text-muted">
          Estimate first, then confirm and start. Every safety check happens on the server; this page shows its answer.
          Your Gemini API key stays on the server and never reaches the browser.
        </p>
      </div>
      <Stepper current={step} />

      {health.status === "error" && <ServerNo error={health.error} />}
      {real && realDisabled && (
        <div data-testid="real-disabled">
          <Alert tone="warning" title="Real Gemini runs are switched off on this server.">
            <p>To enable them, stop the API (Ctrl+C) and start it again with:</p>
            <code className="mt-1 block rounded-md bg-surface px-2 py-1 font-mono text-[13px] text-fg">{SERVE_REAL}</code>
            <p className="mt-1">Each real run still needs your confirmation, a budget and a passing registration check.</p>
          </Alert>
        </div>
      )}
      {real && health.status === "ready" && health.data.real_runs_enabled && (
        <p className="text-sm"><Badge color="blue">REAL runs enabled</Badge> on this server - a started run uses your free-tier quota.</p>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="1 · Configure">
          <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void runEstimate(); }}>
            <Field label="Agent">
              <Select value={form.agent} onChange={(e) => set({ agent: e.target.value as Agent, confirm: false })}>
                {AGENTS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
              </Select>
            </Field>
            <Field label="Suite">
              <Select value={form.suite} onChange={(e) => set({ suite: e.target.value })}>
                {SUITES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Tasks (optional)" hint="comma-separated; empty = the whole suite">
              <Input value={form.tasks} placeholder="e.g. hard-001, hard-007" onChange={(e) => set({ tasks: e.target.value })} />
            </Field>
            <Field label="Repeats (1-10)">
              <Input type="number" min={1} max={10} value={form.repeats} onChange={(e) => set({ repeats: e.target.value })} />
            </Field>
            {real && (
              <Field label="Budget (hard cap on Gemini requests)" hint="the run never sends more requests than this">
                <Input type="number" min={1} value={form.budget} placeholder="e.g. 100" onChange={(e) => set({ budget: e.target.value })} />
              </Field>
            )}
            {request.tasks && (
              <p className="text-sm text-warning-fg sm:col-span-2">
                A subset of tasks is not a full-suite score: it will be shown as a separate marker, never on a trend line.
              </p>
            )}
            <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
              <Button type="submit" variant="primary" disabled={estimate.status === "loading"}>Estimate</Button>
              {stale && <span data-testid="stale" className="text-sm text-muted">The form changed - estimate again before starting.</span>}
            </div>
          </form>
        </Card>

        <Card title="2 · Estimate (nothing is sent to any model)">
          {estimate.status === "idle" && <p className="text-sm text-muted">Press Estimate to ask the server what this run would cost.</p>}
          {estimate.status === "loading" && <Skeleton lines={4} label="Asking the server…" />}
          {estimate.status === "error" && <ServerNo error={estimate.error} />}
          {estimate.status === "ready" && !stale && <EstimatePanel e={estimate.data} />}
          {estimate.status === "ready" && stale && <p className="text-sm text-muted">The form changed after this estimate - estimate again.</p>}
        </Card>
      </div>

      <Card title="3 · Confirm & start">
        <div className="flex flex-col gap-4">
          {real ? (
            <Checkbox label="I confirm: send real requests to Gemini (uses my free-tier quota)" checked={form.confirm}
                      disabled={!fresh && !form.confirm} onChange={(e) => confirm(e.target.checked)} />
          ) : (
            <p className="text-sm text-muted">A SCRIPTED agent sends nothing to any model, so no confirmation is needed.</p>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={() => void runStart()} disabled={!canStart}>
              {real ? "Start REAL run" : "Start scripted run"}
            </Button>
            <span className="text-sm text-muted">
              {!fresh ? "Estimate first." : canStart ? "The server said yes to exactly this request." : "Start is possible only after the server says yes."}
            </span>
          </div>
          {start.status === "loading" && <p role="status" className="text-sm">Starting…</p>}
          {start.status === "error" && (
            <ServerNo error={start.error}>
              {activeJob && <Link to={`/jobs/${activeJob}`} className="mt-2 inline-block font-medium underline">Follow the run in progress</Link>}
            </ServerNo>
          )}
        </div>
      </Card>
    </div>
  );
}

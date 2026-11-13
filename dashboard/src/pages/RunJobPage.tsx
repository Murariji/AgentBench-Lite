// Follow a started run LIVE. Asks GET /runs/{job_id} again every `pollMs` while the job is queued or running
// ("polling") and stops as soon as the server says it is done. Shows the server's own numbers: progress,
// current task and step, requests used (retries included) against the budget. The elapsed clock counts from
// the server's started_at. Nothing is estimated or invented. Job status lives in the server's memory only -
// the RESULTS are stored.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ACTIVE_JOB_STATES, ApiError, api, type Job } from "../api/client";
import { Card } from "../components/Card";
import { Alert, ErrorState, ProgressBar, Skeleton } from "../components/feedback";
import { RUN_STEPS, Stepper } from "../components/Stepper";
import { Badge, KindBadge } from "../components/ui";

type State = { status: "loading" } | { status: "error"; error: ApiError } | { status: "ready"; job: Job };

/** "2:05" from milliseconds (a clock, not a benchmark metric). */
export function clock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "finished") return <Badge color="green">finished</Badge>;
  if (status === "incomplete") return <Badge color="amber">INCOMPLETE</Badge>;
  if (status === "failed") return <Badge color="red">failed</Badge>;
  return <Badge color="blue">{status}</Badge>;
}

/** Ticks every second while the job runs, so the elapsed time visibly moves. */
function useNow(running: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);
  return now;
}

function Live({ job }: { job: Job }) {
  const running = ACTIVE_JOB_STATES.includes(job.status);
  const now = useNow(running);
  const started = job.started_at ? Date.parse(job.started_at) : null;
  const ended = job.finished_at ? Date.parse(job.finished_at) : null;
  const elapsed = started === null ? null : (ended ?? now) - started;
  const position = Math.min(job.completed_tasks + 1, job.total_tasks);

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {running && <span aria-hidden="true" className="live-dot h-2.5 w-2.5 rounded-full bg-accent" />}
          <span className="text-base font-semibold" data-testid="live-status">
            {job.status === "queued" ? "Waiting to start…" : running ? "Running" : job.status === "finished" ? "Finished" : job.status === "incomplete" ? "Stopped early" : "Failed"}
          </span>
          <KindBadge kind={job.kind} />
          <span className="ml-auto text-base font-semibold tabular-nums" data-testid="elapsed">
            {elapsed === null ? "not started yet" : `${running ? "Elapsed" : "Took"} ${clock(elapsed)}`}
          </span>
        </div>

        <p className="text-sm" data-testid="now">
          {running && job.current_task
            ? <>Task {position} of {job.total_tasks}: <span className="font-mono">{job.current_task}</span>
                {job.current_repeat !== null && job.repeats > 1 && ` (repeat ${job.current_repeat})`}
                {job.current_step != null && job.total_steps != null && ` · step ${job.current_step} of max ${job.total_steps}`}</>
            : running ? "Preparing…" : `${job.completed_tasks} of ${job.total_tasks} run(s) executed`}
        </p>
        <ProgressBar percent={job.percent} label="progress" />
        <div className="flex flex-wrap justify-between gap-2 text-sm">
          <span className="text-muted" data-testid="counts">{job.completed_tasks} / {job.total_tasks} runs done</span>
          <span className="tabular-nums" data-testid="requests">
            {job.kind === "real"
              ? `${job.llm_calls_used} / ${job.budget ?? "?"} requests used (retries included)`
              : `${job.llm_calls_used} scripted call(s) - nothing sent to any model`}
          </span>
        </div>
        <ol aria-label="progress lines" className="max-h-72 overflow-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-[13px] leading-6">
          {job.progress.length === 0 && <li className="text-muted">No run finished yet - the first line appears when task 1 is done.</li>}
          {job.progress.map((line, i) => <li key={i}>{line}</li>)}
          {running && job.current_task && <li className="text-muted">{job.current_task} · working…</li>}
        </ol>
        {running && (
          <p className="text-[13px] text-muted">
            You can close this page: the run continues on the server. Find it again on the Overview page. If the API
            stops, the unfinished run is lost (results are saved only when a run finishes).
          </p>
        )}
      </div>
    </Card>
  );
}

function Outcome({ job }: { job: Job }) {
  if (ACTIVE_JOB_STATES.includes(job.status)) return null;
  return (
    <div className="flex flex-col gap-3 text-sm">
      {job.status === "incomplete" && (
        <Alert tone="warning" title="The run stopped early">
          For example the budget or the free-tier quota ran out. What finished is kept and the run is marked
          INCOMPLETE - it is never counted as a full-suite score.
        </Alert>
      )}
      {job.error && <p role="alert" className="rounded-lg bg-danger-bg p-3 text-danger-fg">Error: {job.error}</p>}
      {job.summary && (
        <p data-testid="summary">Server summary: pass rate <strong>{String(job.summary.pass_rate)}</strong>, {String(job.summary.requests)} request(s).</p>
      )}
      {job.saved === true && job.suite_id && (
        <Link to={`/suites/${job.suite_id}`} className="inline-flex h-10 w-fit items-center rounded-lg bg-accent px-4 font-semibold text-on-accent hover:bg-accent/90">
          Open the results ({job.suite_id.slice(0, 8)})
        </Link>
      )}
      {job.saved === false && (
        <div role="alert" className="rounded-lg bg-danger-bg p-3 text-danger-fg">
          <p className="font-semibold">The results could NOT be saved in the database.</p>
          {job.save_error && <p>{job.save_error}</p>}
          {job.recovery_path && <p>A copy was written to: <code>{job.recovery_path}</code></p>}
        </div>
      )}
    </div>
  );
}

export function RunJobPage({ pollMs = 1000 }: { pollMs?: number }) {
  const { jobId = "" } = useParams();
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const job = await api.job(jobId);
        if (!active) return;
        setState({ status: "ready", job });
        if (ACTIVE_JOB_STATES.includes(job.status)) timer = setTimeout(() => void tick(), pollMs);  // ask again
      } catch (e) {
        if (active) setState({ status: "error", error: e instanceof ApiError ? e : new ApiError(0, "client_error", String(e)) });
      }
    };
    void tick();
    return () => { active = false; clearTimeout(timer); };      // leaving the page stops the polling
  }, [jobId, pollMs, attempt]);

  // The browser tab shows the progress too, e.g. "(2/9) Running · AgentBench-Lite".
  const job = state.status === "ready" ? state.job : null;
  useEffect(() => {
    if (job && ACTIVE_JOB_STATES.includes(job.status)) document.title = `(${job.completed_tasks}/${job.total_tasks}) Running · AgentBench-Lite`;
  }, [job]);

  if (state.status === "loading") return <Skeleton lines={5} label="Loading the run…" />;
  if (state.status === "error") {
    return <ErrorState title="Could not load the job" code={state.error.code} message={state.error.message} onRetry={() => setAttempt((n) => n + 1)} />;
  }
  const j = state.job;
  const running = ACTIVE_JOB_STATES.includes(j.status);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <h1 className="flex flex-wrap items-center gap-3 text-title">
          Run job <span className="font-mono">{j.job_id.slice(0, 8)}</span> <StatusBadge status={j.status} />
        </h1>
        <p className="text-muted">
          {j.agent} on {j.suite} · {j.tasks.length} task(s) × {j.repeats} repeat(s)
          {j.budget !== null && ` · budget ${j.budget} requests`}
        </p>
        <Stepper steps={RUN_STEPS} current={running ? 3 : 4} />
      </div>
      <Live job={j} />
      <Outcome job={j} />
      <p className="text-[13px] text-muted">{j.note}</p>
    </div>
  );
}

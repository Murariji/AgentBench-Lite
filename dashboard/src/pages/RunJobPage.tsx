// Step 10.4: follow a started run. Asks GET /runs/{job_id} again every `pollMs` while the job is queued or
// running ("polling"), and stops as soon as the server says it is done. Shows the server's own progress
// numbers and lines; computes nothing. Job status lives in the server's memory only - the RESULTS are stored.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ACTIVE_JOB_STATES, ApiError, api, type Job } from "../api/client";
import { Badge, Card, KindBadge } from "../components/ui";

type State = { status: "loading" } | { status: "error"; error: ApiError } | { status: "ready"; job: Job };

function StatusBadge({ status }: { status: string }) {
  if (status === "finished") return <Badge color="green">finished</Badge>;
  if (status === "incomplete") return <Badge color="amber">INCOMPLETE</Badge>;
  if (status === "failed") return <Badge color="red">failed</Badge>;
  return <Badge color="blue">{status}</Badge>;
}

function Outcome({ job }: { job: Job }) {
  if (ACTIVE_JOB_STATES.includes(job.status)) return null;
  return (
    <div className="space-y-2 text-sm">
      {job.status === "incomplete" && (
        <p className="rounded bg-amber-50 p-2 text-amber-900">
          The run stopped early (for example the budget or the free-tier quota ran out). What finished is kept and
          the run is marked INCOMPLETE - it is never counted as a full-suite score.
        </p>
      )}
      {job.error && <p role="alert" className="rounded bg-red-50 p-2 text-red-800">Error: {job.error}</p>}
      {job.saved === true && job.suite_id && (
        <Link to={`/suites/${job.suite_id}`} className="inline-block rounded bg-slate-900 px-3 py-1 text-white">
          Open the results ({job.suite_id.slice(0, 8)})
        </Link>
      )}
      {job.saved === false && (
        <div role="alert" className="rounded bg-red-50 p-2 text-red-800">
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

  if (state.status === "loading") return <p role="status">Loading…</p>;
  if (state.status === "error") {
    return (
      <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        <p className="font-semibold">Could not load the job ({state.error.code})</p>
        <p className="mt-1">{state.error.message}</p>
        <button onClick={() => setAttempt((n) => n + 1)} className="mt-3 rounded bg-red-700 px-3 py-1 text-white">Try again</button>
      </div>
    );
  }
  const job = state.job;
  return (
    <div className="space-y-4">
      <h2 className="flex flex-wrap items-center gap-2 text-lg font-semibold">
        Run job {job.job_id.slice(0, 8)} <StatusBadge status={job.status} /> <KindBadge kind={job.kind} />
      </h2>
      <Card title="Progress">
        <p className="text-sm">
          {job.agent} on {job.suite} · {job.tasks.length} task(s) × {job.repeats} repeat(s)
          {job.budget !== null && ` · budget ${job.budget} requests`}
        </p>
        <div role="progressbar" aria-label="progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.percent}
             className="mt-2 h-3 w-full rounded bg-slate-100">
          <div className="h-3 rounded bg-sky-600" style={{ width: `${job.percent}%` }} />
        </div>
        <p data-testid="counts" className="mt-1 text-sm text-slate-600">
          {job.completed_tasks} / {job.total_tasks} runs done
          {job.current_task && ` · now: ${job.current_task}${job.current_repeat ? ` (repeat ${job.current_repeat})` : ""}`}
        </p>
        <ol aria-label="progress lines" className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 font-mono text-xs">
          {job.progress.map((line, i) => <li key={i}>{line}</li>)}
        </ol>
      </Card>
      <Outcome job={job} />
      <p className="text-xs text-slate-500">{job.note}</p>
    </div>
  );
}

"""Background benchmark jobs (Phase 9.2): one at a time, tracked IN MEMORY, results saved to SQLite.

    job = manager.start(plan, prepare)       # returns at once; a background thread does the work
    manager.get(job.id)                      # status + structured progress, any time

States:  queued -> running -> finished    (every scheduled run executed and evaluated)
                           -> incomplete  (stopped by budget or quota, or infra errors: finished runs are kept)
                           -> failed      (an unexpected error in the program)

TEMPORARY vs PERMANENT: this job table lives in memory and is gone when the server stops. The benchmark
result itself is saved to SQLite (or, if that fails, to a JSON recovery file) and survives restarts. A
server stopped in the MIDDLE of a run loses that unfinished run - exactly like the command line.

LIVE PROGRESS (redesign R4): each job also reports `current_step` / `total_steps` (the step the agent is on in
the run in progress, and that task's step LIMIT - not a prediction) and `llm_calls_used` (requests sent so far,
EVERY retry included). They are counted by `_ObservedLLM`, a pass-through placed INSIDE the benchmark's
RateLimitedLLM: it only sees calls the hard request budget already reserved, so for a real run
llm_calls_used == the budget's own count. A call the budget refuses is never sent and never counted.
"""

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agentbench.benchmark import LLMFactory
from agentbench.llm.base import LLMClient
from agentbench.metrics import compute_metrics
from agentbench.models import AgentConfig
from agentbench.runs import RunPlan, execute_plan, redact
from agentbench.storage import save_with_recovery

MAX_PROGRESS_LINES = 500
JOB_STATES = ("queued", "running", "finished", "incomplete", "failed")
TEMPORARY_NOTE = ("Job status is kept in memory only and is lost when the server stops. Finished benchmark "
                  "results are saved to SQLite (see /suites) and are not affected by a restart.")


class _ObservedLLM(LLMClient):
    """Passes every call through unchanged and only reports it (before sending, and after a reply)."""

    def __init__(self, inner: LLMClient, on_call: Callable[[], None], on_reply: Callable[[], None]) -> None:
        self._inner, self._on_call, self._on_reply = inner, on_call, on_reply
        self.name = inner.name

    def generate(self, messages, tools, system_prompt=None):
        self._on_call()
        reply = self._inner.generate(messages, tools, system_prompt)
        self._on_reply()                     # only a SUCCESSFUL reply moves to the next step (a retry does not)
        return reply


class RunInProgressError(Exception):
    def __init__(self, active: "Job") -> None:
        super().__init__(f"a benchmark run is already in progress (job {active.id[:8]}, status {active.status})")
        self.active = active


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    id: str
    agent: str
    suite: str
    task_ids: list[str]
    repeats: int
    budget: int | None
    kind: str                                    # "real" | "scripted"
    scheduled: list[tuple[str, int]]             # (task_id, repeat) in execution order
    status: str = "queued"
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: list[str] = field(default_factory=list)
    completed: int = 0                           # executed runs so far (passed, failed or infra error)
    suite_id: str | None = None
    saved: bool | None = None                    # None = not finished yet; False = NOT in SQLite
    save_error: str | None = None
    recovery_path: str | None = None             # exact location of the JSON copy when saving failed
    error: str | None = None
    summary: dict | None = None
    current_step: int | None = None              # 1-based step of the run in progress (None between runs)
    total_steps: int | None = None               # that task's max_steps: a LIMIT, the run may finish earlier
    llm_calls_used: int = 0                      # requests sent so far in this job, retries included

    def snapshot(self) -> dict:
        """A consistent copy for the API (taken under the manager's lock)."""
        total = len(self.scheduled)
        current = self.scheduled[self.completed] if self.status == "running" and self.completed < total else None
        return {
            "job_id": self.id, "status": self.status, "agent": self.agent, "kind": self.kind, "suite": self.suite,
            "tasks": list(self.task_ids), "repeats": self.repeats, "budget": self.budget,
            "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
            "completed_tasks": self.completed, "total_tasks": total,
            "percent": round(100 * self.completed / total, 1) if total else 0.0,
            "current_task": current[0] if current else None,
            "current_repeat": current[1] + 1 if current else None,
            "progress": list(self.progress), "suite_id": self.suite_id, "saved": self.saved,
            "save_error": self.save_error, "recovery_path": self.recovery_path, "error": self.error,
            "summary": dict(self.summary) if self.summary else None, "note": TEMPORARY_NOTE,
            "current_step": self.current_step if self.status == "running" else None,
            "total_steps": self.total_steps if self.status == "running" else None,
            "llm_calls_used": self.llm_calls_used,
        }


class JobManager:
    def __init__(self, *, results_db: Path, recovery_dir: Path,
                 sleep: Callable[[float], None]) -> None:
        self._lock = threading.Lock()            # guards _jobs, _active and every Job field
        self._jobs: dict[str, Job] = {}
        self._active: Job | None = None
        self._results_db = Path(results_db)
        self._recovery_dir = Path(recovery_dir)
        self._sleep = sleep

    # ---------- starting: the check AND the creation happen as ONE step under the lock -------------
    def start(self, plan: RunPlan, prepare: Callable[[], tuple[AgentConfig, LLMFactory]]) -> Job:
        with self._lock:
            if self._active is not None:          # another request got here first
                raise RunInProgressError(self._active)
            job = Job(id=uuid.uuid4().hex, agent=plan.agent, suite=plan.suite, task_ids=[t.id for t in plan.tasks],
                      repeats=plan.repeats, budget=plan.budget, kind="real" if plan.is_real else "scripted",
                      scheduled=[(t.id, r) for t in plan.tasks for r in range(plan.repeats)])
            self._jobs[job.id] = job
            self._active = job
        threading.Thread(target=self._work, args=(job, plan, prepare), name=f"job-{job.id[:8]}",
                         daemon=True).start()
        return job

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            matches = [j for i, j in self._jobs.items() if i.startswith(job_id)]
            return matches[0].snapshot() if len(matches) == 1 else None

    def list(self) -> list[dict]:
        with self._lock:
            return [j.snapshot() for j in sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)]

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._active is not None

    # ---------- the background thread -------------------------------------------------------------
    def _progress(self, job: Job, line: str) -> None:
        line = redact(line)
        with self._lock:
            if line.startswith("["):              # every executed run prints exactly one "[i/n] ..." line
                job.completed += 1
                job.current_step = job.total_steps = None   # that run is over; the next one starts at step 1
            job.progress = (job.progress + [line])[-MAX_PROGRESS_LINES:]

    def _observe(self, job: Job, make_llm: LLMFactory) -> LLMFactory:
        """The same factory, each client wrapped so the job can report live step and request counts."""
        def factory(task, repeat):
            replies = 0

            def on_call() -> None:
                with self._lock:
                    job.llm_calls_used += 1
                    job.current_step = min(replies + 1, task.max_steps)
                    job.total_steps = task.max_steps

            def on_reply() -> None:
                nonlocal replies
                replies += 1
            return _ObservedLLM(make_llm(task, repeat), on_call, on_reply)
        return factory

    def _work(self, job: Job, plan: RunPlan, prepare) -> None:
        with self._lock:
            job.status, job.started_at = "running", _now()
        try:
            config, make_llm = prepare()          # real runs: the Gemini client is built HERE, after all gates
            suite = execute_plan(plan, config, self._observe(job, make_llm), progress=lambda line: self._progress(job, line),
                                 sleep=self._sleep)
        except Exception as exc:                  # a bug, a missing key, ...: never a crash, never a secret
            with self._lock:
                job.status, job.error = "failed", redact(f"{type(exc).__name__}: {exc}")
        else:
            m = compute_metrics(suite)
            summary = {"pass_rate": str(m.pass_rate), "passed": m.passed_runs, "evaluated": m.eligible_runs,
                       "infra_errors": m.infra_errors, "skipped": m.skipped_runs, "complete": m.complete,
                       "stop_reason": suite.stop_reason, "requests": m.total_llm_calls}
            # Persistence is reported SEPARATELY and honestly: saved=True ONLY if SQLite committed.
            outcome = save_with_recovery(suite, self._results_db, self._recovery_dir)
            with self._lock:
                job.status = "finished" if suite.is_complete else "incomplete"   # budget/quota -> incomplete
                job.suite_id, job.summary, job.saved = suite.suite_id, summary, outcome.saved
                job.save_error = redact(outcome.error)
                job.recovery_path = str(Path(outcome.recovery_path).resolve()) if outcome.recovery_path else None
        finally:
            with self._lock:
                job.finished_at = _now()
                if self._active is job:
                    self._active = None

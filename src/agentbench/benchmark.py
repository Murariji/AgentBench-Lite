"""Suite runner: run every task of a suite (x repeats), evaluate, keep EVERY result.

    for each task, for each repeat (sequentially - never in parallel):
        budget too low for a typical task?  -> skip the rest (never start a task we can't afford)
        run = AgentRunner(...).run(task)              # execution (Phase 4)
        if run is an infrastructure error:            # not the agent's fault
            record it as "infra_error", no evaluation
            auth / quota / budget?  -> CIRCUIT BREAKER: skip every remaining run
        else:
            evaluation = evaluate(task, run)          # evaluation (Phase 5)
            record it as "passed" / "failed"

Free-tier safety (Step 6.3): every request goes through RateLimitedLLM (pacing + a HARD
request cap). Nothing is discarded: every scheduled run ends up as a RunRecord or a SkippedRun.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from agentbench.evaluators import evaluate
from agentbench.llm.base import LLMClient
from agentbench.llm.pacing import Pacer, RateLimitedLLM, RequestBudget
from agentbench.models import (AgentConfig, RunRecord, SkippedRun, SuiteResult, Task, _utc_now,
                               is_infra_error)
from agentbench.runner import AgentRunner, RetryPolicy
from agentbench.tools.registry import ToolRegistry

# Builds the LLM for one run. Gets (task, repeat) so a scripted FakeLLM can be created
# per task; a real client (Gemini) can simply return the same object every time.
LLMFactory = Callable[[Task, int], LLMClient]

# After these errors, more requests would fail too (or cost quota): stop the whole suite.
CIRCUIT_BREAKER_KINDS: frozenset[str] = frozenset({"auth", "quota_exhausted", "budget_exhausted"})

TYPICAL_REQUESTS_PER_TASK = 5      # a real Gemini run on a shop task used about 5 requests
ASSUMED_SECONDS_PER_REQUEST = 7.0  # measured: 5 requests took 33.2 s on the free tier


@dataclass(frozen=True)
class RequestEstimate:
    """What a suite run will roughly cost, shown BEFORE any real request is made."""

    runs: int                 # tasks x repeats
    typical_requests: int     # runs x TYPICAL_REQUESTS_PER_TASK
    worst_case_requests: int  # sum(max_steps) x repeats x max_attempts: every step retried
    budget: int | None        # the hard cap (None = no cap)
    estimated_seconds: float  # rough: the expected requests x max(pacing, typical latency)

    @property
    def expected_requests(self) -> int:
        """Typical requests, but never more than the budget allows."""
        return self.typical_requests if self.budget is None else min(self.typical_requests, self.budget)

    def describe(self) -> str:
        cap = "none" if self.budget is None else f"{self.budget} (hard cap: never exceeded)"
        return "\n".join([
            f"Runs       : {self.runs}",
            f"Requests   : about {self.typical_requests} typical "
            f"(~{TYPICAL_REQUESTS_PER_TASK} per run), {self.worst_case_requests} worst case",
            f"Budget     : {cap}",
            f"Time       : about {math.ceil(self.estimated_seconds / 60)} min (rough)",
        ])


def estimate_requests(tasks: list[Task], config: AgentConfig, *, repeats: int = 1,
                      budget: int | None = None) -> RequestEstimate:
    runs = len(tasks) * repeats
    typical = runs * TYPICAL_REQUESTS_PER_TASK
    worst = sum(t.max_steps for t in tasks) * repeats * config.max_attempts
    expected = typical if budget is None else min(typical, budget)
    seconds = expected * max(config.min_interval_seconds, ASSUMED_SECONDS_PER_REQUEST)
    return RequestEstimate(runs, typical, worst, budget, seconds)


def run_suite(
    tasks: list[Task],
    config: AgentConfig,
    make_llm: LLMFactory,
    tools: ToolRegistry,
    *,
    suite_name: str,
    repeats: int = 1,
    dataset: str | None = None,
    request_budget: int | None = None,
    min_requests_to_start: int = TYPICAL_REQUESTS_PER_TASK,
    progress: Callable[[str], None] | None = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.perf_counter,
) -> SuiteResult:
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError(f"task ids must be unique: {ids}")
    say = progress or (lambda _message: None)

    budget = RequestBudget(request_budget) if request_budget is not None else None
    pacer = Pacer(config.min_interval_seconds, sleep=sleep, clock=clock)  # shared by ALL runs
    estimate = estimate_requests(tasks, config, repeats=repeats, budget=request_budget)
    suite = SuiteResult(suite_name=suite_name, config=config, task_ids=ids, repeats=repeats,
                        tasks=tasks, dataset=dataset, request_budget=request_budget,
                        # the estimate only means something for budgeted (real) runs
                        estimated_requests=estimate.expected_requests if budget else None)

    scheduled = [(task, repeat) for task in tasks for repeat in range(repeats)]

    def skip_from(position: int, reason: str) -> None:
        suite.stop_reason = reason
        suite.skipped.extend(SkippedRun(task_id=t.id, repeat=r, reason=reason)
                             for t, r in scheduled[position:])
        say(f"STOPPED: {reason}. {len(scheduled) - position} remaining run(s) skipped, "
            f"0 further requests.")

    for position, (task, repeat) in enumerate(scheduled):
        label = f"[{position + 1}/{len(scheduled)}] {task.id}" + (
            f" (repeat {repeat + 1}/{repeats})" if repeats > 1 else "")

        # Never START a task the remaining budget can't typically cover.
        if budget is not None and budget.remaining < min_requests_to_start:
            skip_from(position, f"request budget: {budget.remaining} of {budget.limit} left, "
                                f"a task typically needs ~{min_requests_to_start}")
            break

        llm = RateLimitedLLM(make_llm(task, repeat), pacer, budget)
        runner = AgentRunner(llm, tools, system_prompt=config.system_prompt,
                             retry=RetryPolicy(max_attempts=config.max_attempts),
                             sleep=sleep, clock=clock)
        run = runner.run(task)

        if is_infra_error(run):
            suite.records.append(RunRecord(task_id=task.id, repeat=repeat, difficulty=task.difficulty,
                                           run=run, outcome="infra_error"))
            what = "STOPPED BY REQUEST BUDGET" if run.error_kind == "budget_exhausted" \
                else f"INFRA ERROR ({run.error_kind})"
            say(f"{label}: {what} - not counted as an agent failure")
            if run.error_kind in CIRCUIT_BREAKER_KINDS:  # the circuit breaker
                skip_from(position + 1, f"{run.error_kind} in {task.id}")
                break
            continue

        evaluation = evaluate(task, run)
        record = RunRecord(task_id=task.id, repeat=repeat, difficulty=task.difficulty,
                           run=run, evaluation=evaluation,
                           outcome="passed" if evaluation.passed else "failed")
        failed = [c.name for c in evaluation.checks if not c.passed]
        say(f"{label}: {record.outcome.upper()}" + (f" (failed: {', '.join(failed)})" if failed else "")
            + f"  [{len(run.trace.steps)} steps, {run.llm_calls} LLM calls, {run.duration_seconds:.1f}s]")
        suite.records.append(record)

    suite.finished_at = _utc_now()
    if not suite.is_complete:
        say("Suite INCOMPLETE: some runs had infrastructure errors or were skipped.")
    return suite

"""Benchmark metrics: calculations over the records we already have. No new measurements.

Definitions (also in the README):
  scheduled   = tasks x repeats
  eligible    = runs that produced an AGENT result (completed or max_steps or an
                unusable model reply) -> these are evaluated
  infra       = runs that ended in an infrastructure error (quota, auth, network...)
                -> NOT evaluated, NOT counted as failures
  skipped     = scheduled runs that never ran
  pass rate   = passed / eligible           (always shown with its denominator)
  averages    = over ELIGIBLE runs (steps, LLM calls, tokens, duration)
  totals      = over ALL executed runs (LLM calls, duration: that's what quota/time cost)
  pass@k      = share of tasks where AT LEAST ONE of the k repeats passed  ("can it?")
  pass^k      = share of tasks where ALL k repeats passed                   ("can I rely on it?")
                both only over tasks whose k repeats were all eligible; simple empirical
                versions (not the unbiased pass@k estimator used for code benchmarks)
"""

from collections import Counter, defaultdict

from pydantic import BaseModel

from agentbench.models import RunRecord, SuiteResult


class Rate(BaseModel):
    passed: int
    eligible: int

    @property
    def rate(self) -> float | None:
        return self.passed / self.eligible if self.eligible else None

    def __str__(self) -> str:
        return f"{self.passed}/{self.eligible} ({self.rate:.1%})" if self.eligible else "0/0 (n/a)"


class SuiteMetrics(BaseModel):
    scheduled_runs: int
    eligible_runs: int
    passed_runs: int
    failed_runs: int
    infra_errors: int
    skipped_runs: int
    complete: bool

    pass_rate: Rate
    by_difficulty: dict[str, Rate]

    avg_steps: float | None
    avg_llm_calls: float | None
    avg_input_tokens: float | None    # None if the provider reported no token counts
    avg_output_tokens: float | None
    avg_duration_seconds: float | None
    total_llm_calls: int              # every real request, including infra-error runs
    total_duration_seconds: float

    tool_calls: int
    tool_errors: int
    failed_checks: list[tuple[str, int]]   # most frequent first

    k: int
    pass_at_k: Rate | None                 # only when repeats > 1
    pass_pow_k: Rate | None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _tokens(record: RunRecord, field: str) -> int | None:
    counts = [getattr(s, field) for s in record.run.trace.steps if getattr(s, field) is not None]
    return sum(counts) if counts else None


def compute_metrics(suite: SuiteResult) -> SuiteMetrics:
    records = suite.records
    eligible = [r for r in records if r.outcome != "infra_error"]
    passed = [r for r in eligible if r.outcome == "passed"]

    by_level: dict[str, list[RunRecord]] = defaultdict(list)
    for r in eligible:
        by_level[r.difficulty or "unrated"].append(r)
    order = ["easy", "medium", "hard", "unrated"]
    by_difficulty = {
        level: Rate(passed=sum(r.outcome == "passed" for r in by_level[level]), eligible=len(by_level[level]))
        for level in order if level in by_level
    }

    calls = [s.tool_call for r in eligible for s in r.run.trace.steps if s.tool_call is not None]
    failed_checks = Counter(
        c.name for r in eligible for c in r.evaluation.checks if not c.passed
    ).most_common()

    in_tokens = [t for r in eligible if (t := _tokens(r, "input_tokens")) is not None]
    out_tokens = [t for r in eligible if (t := _tokens(r, "output_tokens")) is not None]

    pass_at_k = pass_pow_k = None
    if suite.repeats > 1:
        per_task: dict[str, list[RunRecord]] = defaultdict(list)
        for r in records:
            per_task[r.task_id].append(r)
        full = [rs for rs in per_task.values()
                if len(rs) == suite.repeats and all(r.outcome != "infra_error" for r in rs)]
        pass_at_k = Rate(passed=sum(any(r.outcome == "passed" for r in rs) for rs in full), eligible=len(full))
        pass_pow_k = Rate(passed=sum(all(r.outcome == "passed" for r in rs) for rs in full), eligible=len(full))

    return SuiteMetrics(
        scheduled_runs=suite.scheduled_runs,
        eligible_runs=len(eligible),
        passed_runs=len(passed),
        failed_runs=len(eligible) - len(passed),
        infra_errors=len(records) - len(eligible),
        skipped_runs=len(suite.skipped),
        complete=suite.is_complete,
        pass_rate=Rate(passed=len(passed), eligible=len(eligible)),
        by_difficulty=by_difficulty,
        avg_steps=_mean([len(r.run.trace.steps) for r in eligible]),
        avg_llm_calls=_mean([r.run.llm_calls for r in eligible]),
        avg_input_tokens=_mean(in_tokens),
        avg_output_tokens=_mean(out_tokens),
        avg_duration_seconds=_mean([r.run.duration_seconds for r in eligible]),
        total_llm_calls=sum(r.run.llm_calls for r in records),
        total_duration_seconds=sum(r.run.duration_seconds for r in records),
        tool_calls=len(calls),
        tool_errors=sum(c.error is not None for c in calls),
        failed_checks=failed_checks,
        k=suite.repeats,
        pass_at_k=pass_at_k,
        pass_pow_k=pass_pow_k,
    )

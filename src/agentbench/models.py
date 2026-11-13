"""Core data models (the "contracts") used by every part of AgentBench-Lite.

Flow of data:
    Task  ──run──►  Trace (list of Step, each may hold a ToolCall)  ──►  RunResult
    Task + RunResult  ──evaluate──►  EvaluationResult (list of Check)

Execution (RunResult: what happened) and evaluation (EvaluationResult: was it right)
are deliberately separate, linked by ``run_id``.

All models are Pydantic models, so they:
  * validate their data when created (bad data raises ``pydantic.ValidationError``)
  * convert to/from JSON with ``model_dump_json()`` / ``model_validate_json()``
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The only ways a run can END. Whether the answer is CORRECT is decided later by an
# evaluator (Phase 5), so there is deliberately no "success"/"failed" here.
RunStatus = Literal["completed", "max_steps", "error"]

# How a task's final answer is graded (see agentbench/evaluators.py).
AnswerType = Literal["exact", "contains", "number"]

Difficulty = Literal["easy", "medium", "hard"]


def _utc_now() -> datetime:
    """Current time in UTC (timezone-aware, so it is unambiguous when stored)."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """A random unique id, e.g. '9f1c2a7e...' (32 hex characters)."""
    return uuid.uuid4().hex


class _BaseModel(BaseModel):
    """Shared settings for all our models.

    extra="forbid": unknown fields raise an error instead of being silently
    ignored, so a typo like ``promt="..."`` is caught immediately.
    """

    model_config = ConfigDict(extra="forbid")


class Task(_BaseModel):
    """What the agent is asked to do."""

    id: str = Field(min_length=1, description="Unique task id, e.g. 'math-001'.")
    prompt: str = Field(min_length=1, description="Instruction given to the agent.")
    expected_answer: str | None = Field(
        default=None, description="Reference answer, used by evaluators later."
    )
    allowed_tools: list[str] | None = Field(
        default=None,
        description="None = all registered tools; [] = no tools; a list = only those tools.",
    )
    max_steps: int = Field(default=10, gt=0, description="Safety limit for the agent loop.")
    difficulty: Difficulty | None = None  # for per-difficulty pass rates
    # ---- grading rules (used by evaluators, never by the runner) ----
    answer_type: AnswerType = Field(default="exact", description="How the answer is graded.")
    abs_tolerance: float = Field(default=0.0, ge=0, description="number only: allowed absolute difference.")
    rel_tolerance: float = Field(default=0.0, ge=0, description="number only: allowed relative difference.")
    required_tools: list[str] = Field(
        default_factory=list, description="Tools that must be called successfully at least once."
    )


class ToolCall(_BaseModel):
    """One use of a tool: what was called, with what, and what came back."""

    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None  # set if the tool succeeded
    error: str | None = None   # set if the tool failed

    @model_validator(mode="after")
    def _not_both_output_and_error(self) -> "ToolCall":
        # A tool call either succeeded or failed — never both.
        if self.output is not None and self.error is not None:
            raise ValueError("a ToolCall cannot have both 'output' and 'error'")
        return self


class Step(_BaseModel):
    """One turn of the agent loop."""

    index: int = Field(ge=0, description="Position in the trace: 0, 1, 2, ...")
    llm_output: str = Field(description="What the model said/decided on this turn.")
    tool_call: ToolCall | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
    # Token usage reported by the LLM for this turn (None if the provider didn't say).
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Trace(_BaseModel):
    """Full, ordered recording of one run. The central data structure."""

    task_id: str = Field(min_length=1)
    steps: list[Step] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def _steps_in_order(cls, steps: list[Step]) -> list[Step]:
        # Step indexes must be exactly 0, 1, 2, ... with no gaps or reordering.
        for expected, step in enumerate(steps):
            if step.index != expected:
                raise ValueError(
                    f"step indexes must be 0..n-1 in order; "
                    f"found {step.index} at position {expected}"
                )
        return steps


class RetryEvent(_BaseModel):
    """One FAILED LLM request that was retried: what failed, how long we waited, how it ended."""

    step_index: int = Field(ge=0)        # the agent-loop step whose LLM call failed
    attempt: int = Field(ge=1)           # 1 = the first try of that call failed, 2 = the second, ...
    error_kind: str = Field(min_length=1)   # e.g. "server", "rate_limit", "network"
    status_code: int | None = None       # e.g. 503 / 429 (None for network errors)
    waited_seconds: float = Field(ge=0)  # backoff or Retry-After wait before the next attempt
    request_id: str | None = None        # provider's request id, if the provider gave one
    occurred_at: datetime = Field(default_factory=_utc_now)
    succeeded: bool                      # did this LLM call EVENTUALLY succeed after retrying?


class RunResult(_BaseModel):
    """Outcome of running one Task: how it ended, the answer, and the full trace."""

    run_id: str = Field(default_factory=_new_id, min_length=1)  # links evaluations to this run
    task_id: str = Field(min_length=1)
    status: RunStatus
    final_answer: str | None = None
    trace: Trace
    duration_seconds: float = Field(ge=0)
    error: str | None = None       # human-readable reason when status == "error"
    error_kind: str | None = None  # machine-readable, e.g. "quota_exhausted", "auth"
    llm_calls: int = Field(default=0, ge=0)  # real requests made, INCLUDING retries
    # None = NOT RECORDED (runs made before Phase 8 never captured retries; unknown, not zero).
    # []   = recorded, and no request had to be retried.
    retries: list[RetryEvent] | None = None


class Check(_BaseModel):
    """One line on the marksheet: which rule, did it pass, and why."""

    name: str = Field(min_length=1)    # e.g. "status", "answer:number", "required_tools"
    passed: bool
    reason: str = Field(min_length=1)  # always explained, also when it passed


class EvaluationResult(_BaseModel):
    """The verdict for one run. Every check is mandatory: passed = all checks passed."""

    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    passed: bool
    checks: list[Check] = Field(min_length=1)

    @model_validator(mode="after")
    def _verdict_matches_checks(self) -> "EvaluationResult":
        # The verdict is DERIVED from the checks; it can never disagree with them.
        if self.passed != all(check.passed for check in self.checks):
            raise ValueError("'passed' must be True exactly when every check passed")
        return self


# ---------- benchmark runs (Phase 6) -------------------------------------------

# run.error_kind values that are NOT the agent's fault. Such runs are not evaluated and
# do not count toward the pass rate. ("invalid_response" = the model returned an unusable
# reply, and "max_steps" = the agent ran out of steps: both ARE agent results.)
INFRA_ERROR_KINDS: frozenset[str] = frozenset(
    {"auth", "quota_exhausted", "rate_limit", "server", "network", "bad_request", "config",
     "budget_exhausted", "unknown"}
)


def is_infra_error(run: "RunResult") -> bool:
    return run.status == "error" and run.error_kind in INFRA_ERROR_KINDS


class AgentConfig(_BaseModel):
    """One agent setup, described as data, so runs can be compared and reproduced."""

    name: str = Field(min_length=1)                 # e.g. "flash-lite-default"
    provider: Literal["fake", "gemini"]             # "fake" = scripted, NOT a real AI
    model: str = Field(min_length=1)                # actual model id, e.g. "gemini-3.5-flash-lite"
    system_prompt: str
    max_attempts: int = Field(default=3, ge=1)      # LLM retries (see RetryPolicy)
    min_interval_seconds: float = Field(default=0.0, ge=0)  # pacing between requests (Step 6.3)
    prompt_hash: str = ""                           # filled in automatically, see below

    @model_validator(mode="after")
    def _fill_prompt_hash(self) -> "AgentConfig":
        # A short fingerprint of the system prompt: two configs with the same hash used
        # exactly the same prompt, without storing/comparing long texts by eye.
        self.prompt_hash = hashlib.sha256(self.system_prompt.encode("utf-8")).hexdigest()[:12]
        return self

    @property
    def is_scripted(self) -> bool:
        return self.provider == "fake"


RunOutcome = Literal["passed", "failed", "infra_error"]


class RunRecord(_BaseModel):
    """One scheduled run of one task: what happened (run) and the verdict (evaluation)."""

    task_id: str = Field(min_length=1)
    repeat: int = Field(ge=0)                     # 0, 1, 2 ... when a task is repeated
    difficulty: Difficulty | None = None
    run: RunResult
    evaluation: EvaluationResult | None = None    # None ONLY for infrastructure errors
    outcome: RunOutcome

    @model_validator(mode="after")
    def _consistent(self) -> "RunRecord":
        if self.run.task_id != self.task_id:
            raise ValueError("run.task_id must match task_id")
        if self.outcome == "infra_error":
            if not is_infra_error(self.run) or self.evaluation is not None:
                raise ValueError("infra_error records need an infrastructure error and no evaluation")
        else:
            if self.evaluation is None or self.evaluation.run_id != self.run.run_id:
                raise ValueError("passed/failed records need the evaluation of this run")
            if (self.outcome == "passed") != self.evaluation.passed:
                raise ValueError("outcome must agree with evaluation.passed")
        return self


class SkippedRun(_BaseModel):
    """A scheduled run that never happened (e.g. the suite was stopped)."""

    task_id: str = Field(min_length=1)
    repeat: int = Field(ge=0)
    reason: str = Field(min_length=1)


class SuiteResult(_BaseModel):
    """Everything about one suite run. Nothing is discarded: every scheduled run is
    either a record (passed / failed / infra_error) or a skipped entry."""

    # Identifies ONE whole benchmark execution (run_id identifies one task execution inside it,
    # task_id identifies the benchmark task itself).
    suite_id: str = Field(default_factory=_new_id, min_length=1)
    suite_name: str = Field(min_length=1)
    config: AgentConfig
    task_ids: list[str] = Field(min_length=1)   # the scheduled tasks, in order
    repeats: int = Field(default=1, ge=1)
    started_at: datetime = Field(default_factory=_utc_now)
    finished_at: datetime | None = None
    records: list[RunRecord] = Field(default_factory=list)
    skipped: list[SkippedRun] = Field(default_factory=list)
    # For fair comparison and free re-grading later: the FULL task definitions (prompt,
    # expected answer, tolerances, allowed tools, max steps) and which data was used.
    tasks: list[Task] = Field(default_factory=list)
    dataset: str | None = None  # e.g. "shop.db sha256:1a2b3c4d5e6f"
    # Free-tier safety (Step 6.3): the hard request cap, the estimate shown before the run,
    # and why the suite stopped early (None = it didn't).
    request_budget: int | None = Field(default=None, ge=1)
    estimated_requests: int | None = Field(default=None, ge=0)
    stop_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _stable_id_for_old_exports(cls, data: Any) -> Any:
        # JSON exported before suite_id existed: derive the id from the run ids (which are
        # unique), so importing the same old file twice gives the SAME id, never a new one.
        if isinstance(data, dict) and "suite_id" not in data and data.get("records"):
            run_ids = [r.run.run_id if isinstance(r, RunRecord) else r["run"]["run_id"]
                       for r in data["records"]]
            data = {**data, "suite_id": hashlib.sha256("|".join(run_ids).encode()).hexdigest()[:32]}
        return data

    @model_validator(mode="after")
    def _tasks_match_ids(self) -> "SuiteResult":
        if self.tasks and [t.id for t in self.tasks] != self.task_ids:
            raise ValueError("tasks must be the scheduled tasks, in the same order as task_ids")
        return self

    @property
    def tasks_fingerprint(self) -> str | None:
        """Short hash of the full task definitions: same fingerprint = same tasks AND grading."""
        if not self.tasks:
            return None
        text = "\n".join(t.model_dump_json() for t in self.tasks)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    @property
    def scheduled_runs(self) -> int:
        return len(self.task_ids) * self.repeats

    @property
    def is_complete(self) -> bool:
        """Complete = every scheduled run was executed AND evaluated (no infra errors, nothing skipped)."""
        return (not self.skipped
                and len(self.records) == self.scheduled_runs
                and all(r.outcome != "infra_error" for r in self.records))

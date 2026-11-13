"""The API's JSON shapes (its "contract"). FastAPI turns these into the /docs page automatically.

Most responses reuse the framework's own Pydantic models (SuiteResult, RunRecord, SuiteMetrics,
TaskHistoryEntry, SuiteAnalysis ...). The shapes here only add what an API needs: pagination,
summaries, and one consistent error format.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentbench.analysis import RunAnalysis, SuiteAnalysis
from agentbench.metrics import SuiteMetrics
from agentbench.models import AgentConfig, RunRecord, SkippedRun, ToolSpec
from agentbench.storage import TaskHistoryEntry


# ---------- errors: ONE shape for every failure -------------------------------------------

class ErrorBody(BaseModel):
    code: str                        # machine-readable, e.g. "not_found", "ambiguous_id", "validation_error"
    message: str                     # for humans
    details: Any = None              # e.g. which field was invalid


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------- pagination --------------------------------------------------------------------

class Pagination(BaseModel):
    limit: int
    offset: int
    total: int                       # items available in total
    returned: int                    # items in this page
    next_offset: int | None          # None = this is the last page


# ---------- suites ------------------------------------------------------------------------

class RateOut(BaseModel):
    passed: int
    eligible: int
    rate: float | None               # None when nothing was evaluated (never a fake 0%)
    text: str                        # e.g. "9/9 (100.0%)"


class SuiteSummaryOut(BaseModel):
    suite_id: str
    short_id: str
    suite_name: str
    kind: str                        # "real" | "scripted" (scripted = fixed test answers, not AI)
    config_name: str
    provider: str
    model: str
    repeats: int
    started_at: datetime
    finished_at: datetime | None
    scheduled_runs: int
    passed: int
    failed: int
    infra_errors: int                # not agent failures
    skipped: int
    total_llm_calls: int
    pass_rate: RateOut
    complete: bool
    stop_reason: str | None
    # Which task set ran, and is that the whole suite? (added deliberately: contract change 2026-11-13)
    tasks_fingerprint: str | None    # None = task definitions were not stored: the task set is UNKNOWN
    registration_status: Literal["matches", "subset", "differs", "unregistered", "unknown"]
    scope: Literal["full", "subset", "unknown"]   # unknown is NEVER assumed to be "full"
    # Which agent configuration and which tools (contract change 2026-11-13, for comparable chart groups).
    config_fingerprint: str          # AgentConfig.config_fingerprint of the STORED config (same formula everywhere)
    tools_fingerprint: str | None    # None = tools were not recorded for this run (unknown, never invented)


class SuitePage(BaseModel):
    items: list[SuiteSummaryOut]
    pagination: Pagination


class RegistrationOut(BaseModel):
    status: str                      # matches | subset | differs | unregistered
    line: str                        # the same sentence the CLI report prints
    problems: list[str]
    notes: list[str]                 # what could not be checked
    version: int | None = None
    suite_fingerprint: str | None = None


class RunSummaryOut(BaseModel):
    """One run inside a suite, without its trace (fetch /suites/{id}/runs/{run_id} for that)."""

    run_id: str
    task_id: str
    repeat: int
    difficulty: str | None
    outcome: str                     # passed | failed | infra_error
    status: str
    final_answer: str | None
    steps: int
    llm_calls: int
    retries: int | None              # None = not recorded (older runs): unknown, not zero
    duration_seconds: float
    error_kind: str | None
    failed_checks: list[str]


class SuiteDetailOut(BaseModel):
    suite_id: str
    suite_name: str
    kind: str
    config: AgentConfig
    config_fingerprint: str
    repeats: int
    started_at: datetime
    finished_at: datetime | None
    dataset: str | None
    tools: list[ToolSpec] | None     # None = not recorded
    tools_fingerprint: str | None
    tasks_fingerprint: str | None
    request_budget: int | None
    estimated_requests: int | None
    stop_reason: str | None
    complete: bool
    metrics: SuiteMetrics
    registration: RegistrationOut
    runs: list[RunSummaryOut]
    skipped: list[SkippedRun]


class RunDetailOut(BaseModel):
    suite_id: str
    record: RunRecord                # the full trace, every tool call, every check
    analysis: RunAnalysis | None     # None when the suite stored no task definitions


class FailuresOut(BaseModel):
    note: str
    analysis: SuiteAnalysis


# ---------- tasks -------------------------------------------------------------------------

class HistoryPage(BaseModel):
    task_id: str
    items: list[TaskHistoryEntry]
    pagination: Pagination


class MeasureGroupOut(BaseModel):
    provider: str
    model: str
    kind: str
    tools: str                       # tools fingerprint or "unknown"
    calculator: str
    suites: int
    scheduled: int
    passed: int
    evaluated: int
    infra_errors: list[str]
    skipped: int
    avg_llm_calls: float | None
    avg_steps: float | None
    runs_with_round_errors: int
    round_errors: int
    tool_errors: int
    near_step_limit: int
    step_limit_failures: int


class MeasureOut(BaseModel):
    task_id: str
    groups: list[MeasureGroupOut]
    limitations: list[str]


# ---------- comparison --------------------------------------------------------------------

class TaskOutcomesOut(BaseModel):
    task_id: str
    outcomes: list[str]              # first repeat of each suite, in the requested order
    differs: bool


class CompareOut(BaseModel):
    suite_ids: list[str]
    fair: bool
    unfair_dimensions: list[str]
    changed_dimensions: list[str]
    tools_status: str                # same | changed | unknown
    conclusions: list[str]           # the same honest sentences the CLI prints
    dimensions: dict[str, list[str]]
    metrics: list[SuiteMetrics]
    tasks: list[TaskOutcomesOut]


# ---------- misc --------------------------------------------------------------------------

class IndexOut(BaseModel):
    name: str
    version: str
    docs: str
    health: str
    real_runs_enabled: bool
    local_only: str


class HealthOut(BaseModel):
    status: str
    schema_version: int
    real_runs_enabled: bool          # True only if the server was started with --allow-real-runs


class RegisteredSuiteOut(BaseModel):
    suite: str
    version: int
    registered_at: str
    git_head: str | None
    suite_fingerprint: str
    tasks_fingerprint: str
    tools_fingerprint: str
    tools: dict[str, int]
    dataset: str | None
    tasks: list[str]


# ---------- Phase 9.2: estimates and background runs ---------------------------------------------

class RunIn(BaseModel):
    """A request to estimate or start a run. Unknown fields are rejected (422)."""

    model_config = ConfigDict(extra="forbid")

    agent: Literal["careful", "sloppy", "gemini"]    # careful/sloppy = SCRIPTED test agents (not AI)
    suite: str = "shop"
    tasks: list[str] | None = Field(default=None, min_length=1, max_length=20)
    repeats: int = Field(default=1, ge=1, le=10)
    budget: int | None = Field(default=None, ge=1)  # REQUIRED for real runs: the hard request cap
    confirm: bool = False                            # REQUIRED (true) for real runs


class EstimateOut(BaseModel):
    agent: str
    kind: str
    suite: str
    tasks: list[str]
    runs: int
    estimate: dict | None                            # real runs only: typical / worst case / budget / time
    registration: RegistrationOut
    real_runs_enabled: bool
    allowed: bool                                    # would POST /runs accept this request now?
    reasons: list[str]                               # why not (empty when allowed)
    note: str = "An estimate never sends anything to any model."


class JobOut(BaseModel):
    job_id: str
    status: str                                      # queued | running | finished | incomplete | failed
    agent: str
    kind: str
    suite: str
    tasks: list[str]
    repeats: int
    budget: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    completed_tasks: int                             # executed runs so far (for a progress bar)
    total_tasks: int                                 # scheduled runs (tasks x repeats)
    percent: float
    current_task: str | None
    current_repeat: int | None
    progress: list[str]                              # human-readable lines, newest last
    suite_id: str | None
    saved: bool | None                               # True ONLY if stored in SQLite; False = see recovery_path
    save_error: str | None
    recovery_path: str | None
    error: str | None
    summary: dict | None
    note: str                                        # job status is temporary; results are not
    # Live progress (R4). Never invented: null when there is no run in progress.
    current_step: int | None = None                  # 1-based step of the run in progress
    total_steps: int | None = None                   # that task's step LIMIT (max_steps), not a prediction
    llm_calls_used: int = 0                          # requests sent so far in this job, EVERY retry included


class JobPage(BaseModel):
    items: list[JobOut]
    pagination: Pagination

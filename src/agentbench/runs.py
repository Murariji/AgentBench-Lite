"""Shared run orchestration: ONE set of safety rules for the command line and the web API.

    plan = plan_run("gemini", "shop-hard", ["hard-001"], repeats=1, budget=25)   # validate + guard + estimate
    plan.guard.blocks_real_runs     # True -> a real run must be refused (registration differs)
    suite = execute_plan(plan, config, make_llm, progress=print)                 # the actual run

Nothing here sends a request by itself: planning is offline, and a real Gemini client is only created
when a caller explicitly calls gemini_client() - after all of its own checks (CLI: --yes; API: the
four gates in agentbench.api.jobs).
"""

import hashlib
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agentbench.benchmark import LLMFactory, RequestEstimate, estimate_requests, run_suite
from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.models import AgentConfig, SuiteResult, Task
from agentbench.registration import GuardResult, check_suite
from agentbench.runner import DEFAULT_SYSTEM_PROMPT
from agentbench.suites import GRADING_PROBES, SUITES, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

GEMINI_PACING_SECONDS = 6.0   # <= 10 requests per minute
DEFAULT_BUDGET = 80
AGENTS = ("careful", "sloppy", "gemini")   # careful/sloppy = SCRIPTED test agents, gemini = the real model


class RunRequestError(ValueError):
    """An invalid run request (unknown suite/task, bad repeats ...). `field` names the culprit."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


# ---------- Gemini setup (moved here from scripts/run_benchmark.py) --------------------------------

def gemini_client():
    """Build the real client. Call ONLY after every safety check. Building it sends no request."""
    from dotenv import find_dotenv, load_dotenv

    from agentbench.llm.gemini import GeminiClient

    load_dotenv(find_dotenv(usecwd=True))
    return GeminiClient()


def gemini_config(model: str = "see .env / default") -> AgentConfig:
    return AgentConfig(name="gemini-default", provider="gemini", model=model,
                       system_prompt=DEFAULT_SYSTEM_PROMPT, max_attempts=3,
                       min_interval_seconds=GEMINI_PACING_SECONDS)


# ---------- planning: validate, guard, estimate (offline) ----------------------------------------------

def dataset_fingerprint(db_path: Path = DEFAULT_DB_PATH) -> str:
    if not Path(db_path).exists():
        build_shop_db(db_path)            # only builds when missing; never overwrites (offline)
    return f"{Path(db_path).name} sha256:{hashlib.sha256(Path(db_path).read_bytes()).hexdigest()[:12]}"


def select_tasks(suite: str, task_ids: list[str] | None) -> list[Task]:
    if suite not in SUITES:
        raise RunRequestError("suite", f"unknown suite {suite!r}; available: {', '.join(sorted(SUITES))}")
    suite_tasks = SUITES[suite]
    if task_ids:
        known = [t.id for t in suite_tasks]
        unknown = [t for t in task_ids if t not in known]
        if unknown:
            raise RunRequestError("tasks", f"unknown task id(s) for suite {suite}: {', '.join(unknown)}. "
                                           f"Known: {', '.join(known)}")
        if len(set(task_ids)) != len(task_ids):
            raise RunRequestError("tasks", "each task id may be given only once")
    # Selected tasks keep the suite's own order. A subset has its own tasks fingerprint.
    return [t for t in suite_tasks if not task_ids or t.id in task_ids]


@dataclass
class RunPlan:
    agent: str
    suite: str
    tasks: list[Task]
    repeats: int
    budget: int | None           # the HARD cap for real runs (None for scripted runs)
    dataset: str
    guard: GuardResult
    estimate: RequestEstimate | None   # real runs only
    db_path: Path

    @property
    def is_real(self) -> bool:
        return self.agent == "gemini"

    @property
    def total_runs(self) -> int:
        return len(self.tasks) * self.repeats


def plan_run(agent: str, suite: str, task_ids: list[str] | None = None, *, repeats: int = 1,
             budget: int | None = None, db_path: Path = DEFAULT_DB_PATH) -> RunPlan:
    """Validate a run request and check it against its registration. Never sends anything."""
    if agent not in AGENTS:
        raise RunRequestError("agent", f"unknown agent {agent!r}; available: {', '.join(AGENTS)}")
    if repeats < 1:
        raise RunRequestError("repeats", "repeats must be at least 1")
    if budget is not None and budget < 1:
        raise RunRequestError("budget", "budget must be at least 1")
    tasks = select_tasks(suite, task_ids)
    dataset = dataset_fingerprint(db_path)
    with ReadOnlySQLite(db_path) as db:
        tool_specs = shop_registry(db).specs()
    guard = check_suite(suite, tasks, tool_specs, dataset, grading=GRADING_PROBES.get(suite))
    real = agent == "gemini"
    estimate = estimate_requests(tasks, gemini_config(), repeats=repeats, budget=budget) if real else None
    return RunPlan(agent=agent, suite=suite, tasks=tasks, repeats=repeats, budget=budget if real else None,
                   dataset=dataset, guard=guard, estimate=estimate, db_path=Path(db_path))


def scripted_parts(kind: str) -> tuple[AgentConfig, LLMFactory]:
    """Config + LLM factory of a SCRIPTED agent (fixed answers written in advance - not AI)."""
    return scripted_config(kind), scripted_agent(kind)


# ---------- execution ---------------------------------------------------------------------------------

def execute_plan(plan: RunPlan, config: AgentConfig, make_llm: LLMFactory, *,
                 progress: Callable[[str], None] | None = print,
                 sleep: Callable[[float], None] = time.sleep) -> SuiteResult:
    """Run a planned suite with the SAME protections everywhere: pacing (config), the hard request budget
    (real runs), the circuit breaker, infra errors kept apart. Returns the result; does not save it."""
    with ReadOnlySQLite(plan.db_path) as db:
        return run_suite(plan.tasks, config, make_llm, shop_registry(db), suite_name=plan.suite,
                         repeats=plan.repeats, dataset=plan.dataset,
                         request_budget=plan.budget if plan.is_real else None, progress=progress, sleep=sleep)


# ---------- secrets never leave the program -------------------------------------------------------------

_SECRET_NAME = re.compile(r"KEY|SECRET|TOKEN|PASSWORD", re.IGNORECASE)
_GOOGLE_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-]{10,}")


def redact(text: str | None) -> str | None:
    """Remove API keys and other secrets from a message before it is shown or returned."""
    if text is None:
        return None
    for name, value in os.environ.items():
        if _SECRET_NAME.search(name) and value and len(value) >= 8:
            text = text.replace(value, "[redacted]")
    return _GOOGLE_KEY.sub("[redacted]", text)

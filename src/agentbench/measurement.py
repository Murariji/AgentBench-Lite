"""Before/after measurement of ONE task, grouped by tools version (Step A.3). Stored runs only: no API calls.

    groups = measure_task(store, "shop-010")      # one group per (provider, model, tools)
    print(format_measurement("shop-010", groups))

Groups are (provider, model, tools): a column never mixes a scripted agent with a real model, or two
models - only runs of the SAME agent are compared across tools versions.

Reported per group: correctness, average LLM calls and steps, round() errors, other tool errors,
near-step-limit runs and step-limit failures. Infrastructure errors (quota, network, ...) and skipped
runs are counted SEPARATELY and never enter correctness or averages: they are not agent answers.

This is EXPLORATORY evidence for a handful of runs, not statistical proof - the output says so.
"""

from dataclasses import dataclass, field

from agentbench.models import RunRecord, SuiteResult
from agentbench.storage import ResultStore

UNKNOWN = "unknown"
# Always shown with a measurement (CLI and API), after the sample-size line.
MEASURE_LIMITATIONS = [
    "'unknown' = tools were not recorded for those runs; they are not assumed to be any version.",
    "Compare only columns of the SAME agent; scripted columns follow a fixed script (not AI).",
    "A tools change can bundle behaviour AND description changes; the effect is their combination.",
    "Runs on different days can differ for reasons outside our control (the provider's model).",
    "Infrastructure errors and skipped runs are excluded from correctness and averages.",
]


@dataclass
class ToolGroupStats:
    provider: str                    # "fake" = scripted test agent, never mixed with a real model
    model: str
    tools: str                       # tools fingerprint, or "unknown" (not recorded)
    calculator: str                  # e.g. "calculator v2", or "unknown"
    scheduled: int = 0
    passed: int = 0
    failed: int = 0
    infra_errors: list[str] = field(default_factory=list)   # error kinds, e.g. ["quota_exhausted"]
    skipped: int = 0
    llm_calls: list[int] = field(default_factory=list)      # eligible runs only
    steps: list[int] = field(default_factory=list)
    runs_with_round_errors: int = 0
    round_errors: int = 0
    tool_errors: int = 0
    near_step_limit: int = 0
    step_limit_failures: int = 0
    suites: set[str] = field(default_factory=set)

    @property
    def eligible(self) -> int:
        return self.passed + self.failed

    @staticmethod
    def _avg(values: list[int]) -> str:
        return f"{sum(values) / len(values):.2f}" if values else "n/a"


def _round_error(call) -> bool:
    return (call.tool_name == "calculator" and call.error is not None
            and "round(" in str(call.arguments.get("expression", "")))


def measure_task(store: ResultStore, task_id: str) -> list[ToolGroupStats]:
    groups: dict[str, ToolGroupStats] = {}
    suites: dict[str, SuiteResult] = {}
    for entry in store.task_history(task_id):
        tools = entry.tools_fingerprint or UNKNOWN
        key = (entry.provider, entry.model, tools)
        if key not in groups:
            calc = next((f"calculator v{t.version}" for t in entry.tools or [] if t.name == "calculator"), UNKNOWN)
            groups[key] = ToolGroupStats(provider=entry.provider, model=entry.model, tools=tools, calculator=calc)
        g = groups[key]
        g.scheduled += 1
        g.suites.add(entry.suite_id)
        if entry.outcome == "skipped":
            g.skipped += 1
            continue
        if entry.outcome == "infra_error":             # NOT an agent answer: kept apart
            g.infra_errors.append(entry.error_kind or "unknown")
            continue
        suite = suites.setdefault(entry.suite_id, store.load(entry.suite_id))
        record: RunRecord = next(r for r in suite.records if r.task_id == task_id and r.repeat == entry.repeat)
        task = next((t for t in suite.tasks if t.id == task_id), None)
        run = record.run
        calls = [s.tool_call for s in run.trace.steps if s.tool_call]
        g.passed += record.outcome == "passed"
        g.failed += record.outcome == "failed"
        g.llm_calls.append(run.llm_calls)
        g.steps.append(len(run.trace.steps))
        rounds = sum(_round_error(c) for c in calls)
        g.round_errors += rounds
        g.runs_with_round_errors += rounds > 0
        g.tool_errors += sum(c.error is not None for c in calls)
        if task is not None and len(run.trace.steps) >= task.max_steps - 1:
            g.near_step_limit += 1
        g.step_limit_failures += run.status == "max_steps"
    # real models before scripted agents; within an agent: unknown (historical) tools first
    return sorted(groups.values(), key=lambda g: (g.provider == "fake", g.provider, g.model, g.tools != UNKNOWN))


def format_measurement(task_id: str, groups: list[ToolGroupStats]) -> str:
    if not groups:
        return f"No stored runs of {task_id!r}."
    lines = [f"Exploratory before/after for {task_id}, grouped by agent and tools "
             f"(stored runs only, no API calls)", ""]

    def row(label, values):
        lines.append(f"{label:28}" + "".join(f"{v:>30}" for v in values))

    row("agent", [("SCRIPTED " if g.provider == "fake" else "") + g.model[:21] for g in groups])
    row("tools", [f"{g.tools[:8]} ({g.calculator})" if g.tools != UNKNOWN else "unknown (not recorded)"
                  for g in groups])
    row("suites / scheduled runs", [f"{len(g.suites)} / {g.scheduled}" for g in groups])
    row("correct (of evaluated)", [f"{g.passed}/{g.eligible}" for g in groups])
    row("infra errors (not counted)", [(f"{len(g.infra_errors)} (" + ", ".join(sorted(set(g.infra_errors))) + ")")
                                       if g.infra_errors else "0" for g in groups])
    row("skipped (not run)", [str(g.skipped) for g in groups])
    row("avg LLM calls", [g._avg(g.llm_calls) for g in groups])
    row("avg steps", [g._avg(g.steps) for g in groups])
    row("runs with round() errors", [f"{g.runs_with_round_errors}/{g.eligible} ({g.round_errors} errors)" for g in groups])
    row("tool errors (all tools)", [str(g.tool_errors) for g in groups])
    row("near step limit (>= max-1)", [f"{g.near_step_limit}/{g.eligible}" for g in groups])
    row("step-limit failures", [f"{g.step_limit_failures}/{g.eligible}" for g in groups])
    lines += [
        "",
        "LIMITATIONS - read before drawing conclusions:",
        f"  * Tiny samples ({', '.join(f'{g.eligible} evaluated' for g in groups)}): exploratory evidence, "
        "not statistical proof.",
        *(f"  * {text}" for text in MEASURE_LIMITATIONS),
    ]
    return "\n".join(lines)

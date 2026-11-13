"""Failure analysis: WHY did a run fail? Deterministic rules over the stored trace. No LLM, ₹0.

    analyze_run(task, record)  -> RunAnalysis   (primary category + signals + warnings)
    analyze_suite(suite)       -> SuiteAnalysis (counts, examples, warnings over all runs)

Each detector looks at OBSERVABLE evidence (status, tool calls, tool outputs, the answer) and
returns Signals with that evidence. The primary category is the first detected category in
PRIORITY; everything else stays visible as an additional signal (symptoms, side effects).

Honest limits: the rules see WHAT happened, never what the model "thought". A category is the
most likely failure pattern supported by the trace; when the evidence isn't enough, the answer
is "unclassified" - never a guess. Infrastructure errors are not agent failures and get no category.
Nothing here is stored: old runs are re-analysed for free whenever the rules improve.
"""

import json
import re
from collections import Counter
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from agentbench.evaluators import allowed_difference, check_contains, extract_number, normalize_text, numbers_in
from agentbench.models import RunRecord, RunResult, SuiteResult, Task, ToolCall

FailureCategory = Literal[
    "invalid_response", "no_data_used", "tool_misuse", "loop", "unrecovered_tool_error",
    "step_limit", "misread_result", "wrong_result", "unparseable_answer", "unclassified",
]

# THE priority order (root causes before symptoms). The first category with a signal wins.
PRIORITY: tuple[FailureCategory, ...] = (
    "invalid_response",        # the model produced no usable reply
    "no_data_used",            # a required tool was never even tried: the answer is a guess
    "tool_misuse",             # a tool call that could not run at all (unknown / not allowed / bad args)
    "loop",                    # the same call repeated >= LOOP_THRESHOLD times
    "unrecovered_tool_error",  # a tool failed and that tool never worked afterwards
    "step_limit",              # ran out of steps, no deeper cause found
    "misread_result",          # the right value was in the final tool output; the answer differs
    "wrong_result",            # the answer repeats a tool result that was itself wrong
    "unparseable_answer",      # no clear number could be read from the answer
)
LOOP_THRESHOLD = 3
SMALL_OUTPUT_VALUES = 6        # misread only on outputs this small: otherwise a match may be chance
_SQL_FOOTER = re.compile(r"^\(\d+ rows?\)$")
# Exact message prefixes written by ToolRegistry.execute() and AgentRunner._run_tool():
_MISUSE = (re.compile(r"^unknown tool "), re.compile(r"^tool '.*' is not allowed"), re.compile(r"^bad arguments: "))


class Signal(BaseModel):
    """One observation, with the evidence that supports it."""

    name: str                       # a category name, or a symptom like "no_final_answer"
    evidence: str
    step_indexes: list[int] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)


class RunAnalysis(BaseModel):
    run_id: str
    task_id: str
    repeat: int
    outcome: str                                # passed | failed | infra_error
    category: FailureCategory | None = None     # None for passed runs and infrastructure errors
    signals: list[Signal] = Field(default_factory=list)   # everything detected (incl. the primary)
    warnings: list[Signal] = Field(default_factory=list)  # near misses: never change the outcome
    retries_recorded: bool                      # False = run from before retries were captured

    @property
    def primary(self) -> Signal | None:
        return next((s for s in self.signals if s.name == self.category), None)

    @property
    def additional_signals(self) -> list[Signal]:
        return [s for s in self.signals if s.name != self.category]


class SuiteAnalysis(BaseModel):
    suite_id: str
    runs: list[RunAnalysis]
    category_counts: dict[str, int]             # failed runs per primary category
    warning_counts: dict[str, int]              # runs per warning
    failed_runs: int
    passed_runs: int
    infra_errors: int                           # NOT agent failures, listed separately
    skipped_runs: int
    retries_not_recorded: int                   # runs whose retries are unknown (not zero)

    def examples(self, category: str, limit: int = 2) -> list[RunAnalysis]:
        return [r for r in self.runs if r.category == category][:limit]


# ---------- small helpers over the trace -------------------------------------------

def _calls(run: RunResult) -> list[tuple[int, ToolCall]]:
    return [(s.index, s.tool_call) for s in run.trace.steps if s.tool_call is not None]


def _cells(output: str) -> list[str]:
    """Values in a tool output. SQL tables: header line and '(N rows)' footer removed."""
    lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
    if lines and _SQL_FOOTER.match(lines[-1]):
        lines = lines[1:-1]
    return [cell.strip() for line in lines for cell in line.split("|") if cell.strip()]


def _normalize_call(call: ToolCall) -> str:
    """Same tool + same arguments, ignoring whitespace and a trailing ';' in text values."""
    def norm(value):
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip().rstrip(";").strip()
        if isinstance(value, dict):
            return {k: norm(v) for k, v in value.items()}
        if isinstance(value, list):
            return [norm(v) for v in value]
        return value
    return call.tool_name.strip().casefold() + json.dumps(norm(call.arguments), sort_keys=True)


def _expected_in(task: Task, cells: list[str]) -> bool:
    """Is the task's correct answer one of these values? (numbers: within the task's tolerance)"""
    if task.answer_type == "number":
        target = extract_number(task.expected_answer).value
        if target is None:
            return False
        allowed = allowed_difference(target, task.abs_tolerance, task.rel_tolerance)
        return any(abs(n - target) <= allowed for cell in cells for n in numbers_in(cell))
    expected = normalize_text(task.expected_answer)
    return any(normalize_text(cell) == expected or check_contains(task.expected_answer, cell).passed
               for cell in cells)


def _answer_traced_to(task: Task, answer: str, cells: list[str]) -> bool:
    """Did the final answer repeat a value from this output? (numbers: at the answer's precision)"""
    if task.answer_type == "number":
        value = extract_number(answer).value
        if value is None:
            return False
        precision = Decimal(1).scaleb(value.as_tuple().exponent)    # "16107" -> 1, "-19.2" -> 0.1
        return any(n.quantize(precision) == value for cell in cells for n in numbers_in(cell))
    words = [c for c in cells if not numbers_in(c) and len(c) >= 2]
    return any(check_contains(cell, answer).passed for cell in words)


# ---------- detectors: one per category (each returns signals with evidence) ------------

def _invalid_response(task: Task, run: RunResult) -> list[Signal]:
    if run.status == "error" and run.error_kind == "invalid_response":
        return [Signal(name="invalid_response", evidence=f"the model's reply was unusable: {run.error}",
                       step_indexes=[len(run.trace.steps)])]
    return []


def _no_data_used(task: Task, run: RunResult) -> list[Signal]:
    called = {c.tool_name for _, c in _calls(run)}
    never = [t for t in task.required_tools if t not in called]
    if not never:
        return []
    note = ("; the final answer was given without that data" if run.final_answer is not None
            else "; no final answer either")
    return [Signal(name="no_data_used", tool_names=never,
                   evidence=f"required tool(s) {', '.join(never)} never called{note}")]


def _tool_misuse(task: Task, run: RunResult) -> list[Signal]:
    bad = [(i, c) for i, c in _calls(run) if c.error and any(p.match(c.error) for p in _MISUSE)]
    if not bad:
        return []
    first = bad[0][1]
    return [Signal(name="tool_misuse", step_indexes=[i for i, _ in bad], tool_names=sorted({c.tool_name for _, c in bad}),
                   evidence=f"{len(bad)} tool call(s) could not run; e.g. step {bad[0][0]}: {first.error}")]


def _loop(task: Task, run: RunResult) -> list[Signal]:
    seen: dict[str, list[int]] = {}
    names: dict[str, str] = {}
    for index, call in _calls(run):
        key = _normalize_call(call)
        seen.setdefault(key, []).append(index)
        names[key] = call.tool_name
    repeated = [(key, steps) for key, steps in seen.items() if len(steps) >= LOOP_THRESHOLD]
    if not repeated:
        return []
    key, steps = max(repeated, key=lambda kv: len(kv[1]))
    call = next(c for i, c in _calls(run) if i == steps[0])
    return [Signal(name="loop", step_indexes=steps, tool_names=[names[key]],
                   evidence=f"the same call {call.tool_name}({json.dumps(call.arguments)[:120]}) "
                            f"was made {len(steps)} times (steps {', '.join(map(str, steps))})")]


def _unrecovered_tool_error(task: Task, run: RunResult) -> list[Signal]:
    calls = _calls(run)
    unrecovered = []
    for tool in sorted({c.tool_name for _, c in calls if c.error}):
        attempts = [(i, c) for i, c in calls if c.tool_name == tool]
        last_error = max(i for i, c in attempts if c.error)
        if not any(c.error is None and i > last_error for i, c in attempts):   # never worked afterwards
            unrecovered.append((tool, last_error, next(c for i, c in attempts if i == last_error).error))
    if not unrecovered:
        return []
    tool, step, error = unrecovered[0]
    return [Signal(name="unrecovered_tool_error", step_indexes=[s for _, s, _ in unrecovered],
                   tool_names=[t for t, _, _ in unrecovered],
                   evidence=f"step {step}: {tool} failed ({error[:120]}) and {tool} never succeeded afterwards")]


def _step_limit(task: Task, run: RunResult) -> list[Signal]:
    if run.status == "max_steps":
        return [Signal(name="step_limit", evidence=f"used all {task.max_steps} steps without a final answer",
                       step_indexes=[len(run.trace.steps) - 1])]
    return []


def _last_output(run: RunResult) -> tuple[int, ToolCall] | None:
    successes = [(i, c) for i, c in _calls(run) if c.error is None and c.output is not None]
    return successes[-1] if successes else None


def _answer_was_read(task: Task, run: RunResult) -> bool:
    return run.final_answer is not None and (task.answer_type != "number"
                                              or extract_number(run.final_answer).value is not None)


def _misread_result(task: Task, run: RunResult) -> list[Signal]:
    last = _last_output(run)
    if last is None or not _answer_was_read(task, run):
        return []
    step, call = last
    cells = _cells(call.output)
    if len(cells) <= SMALL_OUTPUT_VALUES and _expected_in(task, cells):
        return [Signal(name="misread_result", step_indexes=[step], tool_names=[call.tool_name],
                       evidence=f"the final tool output (step {step}, {call.tool_name}) contained the correct "
                                f"value {task.expected_answer!r}, but the answer was {run.final_answer!r}")]
    return []


def _wrong_result(task: Task, run: RunResult) -> list[Signal]:
    if not _answer_was_read(task, run):
        return []
    last = _last_output(run)
    if last is not None and _expected_in(task, _cells(last[1].output)):
        return []   # the right value WAS there: that's a misread (or chance), not a wrong result
    for step, call in reversed([(i, c) for i, c in _calls(run) if c.error is None and c.output]):
        if _answer_traced_to(task, run.final_answer, _cells(call.output)):
            return [Signal(name="wrong_result", step_indexes=[step], tool_names=[call.tool_name],
                           evidence=f"the answer {run.final_answer!r} repeats the result of step {step} "
                                    f"({call.tool_name}), which did not contain the correct value "
                                    f"{task.expected_answer!r}: the query/calculation was likely wrong")]
    return []


def _unparseable_answer(task: Task, run: RunResult) -> list[Signal]:
    if task.answer_type == "number" and run.final_answer is not None:
        parsed = extract_number(run.final_answer)
        if parsed.value is None:     # the evaluator's own parser: one set of rules
            return [Signal(name="unparseable_answer",
                           evidence=f"answer {run.final_answer!r}: {parsed.reason}")]
    return []


DETECTORS = {
    "invalid_response": _invalid_response, "no_data_used": _no_data_used, "tool_misuse": _tool_misuse,
    "loop": _loop, "unrecovered_tool_error": _unrecovered_tool_error, "step_limit": _step_limit,
    "misread_result": _misread_result, "wrong_result": _wrong_result, "unparseable_answer": _unparseable_answer,
}
assert tuple(DETECTORS) == PRIORITY  # one detector per category, in priority order


def choose_primary(signal_names: list[str]) -> FailureCategory:
    """The first category in PRIORITY that was detected; 'unclassified' if none."""
    return next((c for c in PRIORITY if c in signal_names), "unclassified")


# ---------- symptoms and near-miss warnings ----------------------------------------------

def _symptoms(task: Task, run: RunResult) -> list[Signal]:
    out = []
    if run.final_answer is None:
        out.append(Signal(name="no_final_answer", evidence="the run ended without a final answer"))
    return out


def _warnings(task: Task, run: RunResult) -> list[Signal]:
    warnings = []
    used = len(run.trace.steps)
    if used >= task.max_steps - 1:
        warnings.append(Signal(name="near_step_limit", step_indexes=[used - 1],
                               evidence=f"used {used} of {task.max_steps} allowed steps"))
    calls = _calls(run)
    recovered = [(i, c) for i, c in calls
                 if c.error and any(d.error is None and j > i and d.tool_name == c.tool_name for j, d in calls)]
    if recovered:
        i, c = recovered[0]
        warnings.append(Signal(name="recovered_tool_errors", step_indexes=[i for i, _ in recovered],
                               tool_names=sorted({c.tool_name for _, c in recovered}),
                               evidence=f"{len(recovered)} tool error(s) later fixed; e.g. step {i}: "
                                        f"{c.tool_name} - {c.error[:100]}"))
    unfixed = [(i, c) for i, c in calls if c.error and (i, c) not in recovered]
    if unfixed:   # found in real data: a failed calculator call that was simply ignored (run still passed)
        i, c = unfixed[0]
        warnings.append(Signal(name="unfixed_tool_errors", step_indexes=[i for i, _ in unfixed],
                               tool_names=sorted({c.tool_name for _, c in unfixed}),
                               evidence=f"{len(unfixed)} tool error(s) never fixed; e.g. step {i}: "
                                        f"{c.tool_name} - {c.error[:100]}"))
    if run.retries:
        kinds = Counter(r.error_kind for r in run.retries)
        warnings.append(Signal(name="llm_retries", step_indexes=sorted({r.step_index for r in run.retries}),
                               evidence=f"{len(run.retries)} LLM request(s) retried ("
                                        + ", ".join(f"{k} x{n}" for k, n in kinds.items()) + ")"))
    elif run.retries is None and run.status in ("completed", "max_steps") and run.llm_calls > used:
        # Old runs: retries weren't recorded, but extra LLM calls show some LIKELY happened.
        warnings.append(Signal(name="unrecorded_retries_likely",
                               evidence=f"{run.llm_calls} LLM calls for {used} steps; retries were not "
                                        f"recorded for this run, so details are unknown"))
    return warnings


# ---------- public API ----------------------------------------------------------------------

def analyze_run(task: Task, record: RunRecord) -> RunAnalysis:
    run = record.run
    if task.id != record.task_id:
        raise ValueError(f"record is for task {record.task_id!r}, not {task.id!r}")
    base = dict(run_id=run.run_id, task_id=task.id, repeat=record.repeat, outcome=record.outcome,
                retries_recorded=run.retries is not None)
    if record.outcome == "infra_error":     # not the agent's fault: no category, no agent warnings
        return RunAnalysis(**base)
    warnings = _warnings(task, run)
    if record.outcome == "passed":
        return RunAnalysis(**base, warnings=warnings)
    signals = [s for detect in DETECTORS.values() for s in detect(task, run)] + _symptoms(task, run)
    category = choose_primary([s.name for s in signals])
    if category == "unclassified":
        failed = [c.name for c in record.evaluation.checks if not c.passed]
        signals.append(Signal(name="unclassified",
                              evidence="failed checks: " + ", ".join(failed) + "; the trace does not show a "
                                       "clear pattern (e.g. the answer is not traceable to any tool output)"))
    return RunAnalysis(**base, category=category, signals=signals, warnings=warnings)


def analyze_suite(suite: SuiteResult) -> SuiteAnalysis:
    if not suite.tasks:
        raise ValueError("this suite result has no task definitions, so it cannot be analysed")
    tasks = {t.id: t for t in suite.tasks}
    runs = [analyze_run(tasks[r.task_id], r) for r in suite.records]
    categories = Counter(r.category for r in runs if r.category)
    warnings = Counter(w.name for r in runs for w in r.warnings)
    return SuiteAnalysis(
        suite_id=suite.suite_id, runs=runs,
        category_counts={c: categories[c] for c in (*PRIORITY, "unclassified") if categories[c]},
        warning_counts=dict(warnings.most_common()),
        failed_runs=sum(r.outcome == "failed" for r in runs),
        passed_runs=sum(r.outcome == "passed" for r in runs),
        infra_errors=sum(r.outcome == "infra_error" for r in runs),
        skipped_runs=len(suite.skipped),
        retries_not_recorded=sum(not r.retries_recorded for r in runs if r.outcome != "infra_error"),
    )

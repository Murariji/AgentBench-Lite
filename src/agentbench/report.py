"""Human-readable reports, fair side-by-side comparisons, and JSON export.

Fair comparison rule: same tasks (and grading), same dataset, same repeats; ideally ONE
configuration dimension changed. The comparison says plainly when that isn't true.
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from agentbench.analysis import RunAnalysis, analyze_suite
from agentbench.metrics import SuiteMetrics, compute_metrics
from agentbench.models import SuiteResult

EXPORT_FORMAT = "agentbench-suite-result/1"
RESULTS_DIR = Path("results")  # git-ignored

# Configuration dimensions that can change an agent's behaviour (the name is only a label).
CONFIG_DIMENSIONS = {
    "provider": lambda s: s.config.provider,
    "model": lambda s: s.config.model,
    "system prompt (hash)": lambda s: s.config.prompt_hash,
    "max LLM attempts": lambda s: s.config.max_attempts,
    "request pacing (s)": lambda s: s.config.min_interval_seconds,
}
# Must be identical for the comparison to be fair at all.
FAIRNESS_DIMENSIONS = {
    "tasks + grading (fingerprint)": lambda s: s.tasks_fingerprint,
    "dataset": lambda s: s.dataset,
    "repeats": lambda s: s.repeats,
}


def agent_kind(suite: SuiteResult) -> str:
    if suite.config.is_scripted:
        return "SCRIPTED AGENT (not a real AI - fixed answers written in advance)"
    return f"REAL LLM ({suite.config.provider}: {suite.config.model})"


def _num(value: float | None, fmt: str = ".1f") -> str:
    return "n/a" if value is None else format(value, fmt)


def _tools_summary(suite: SuiteResult) -> str:
    if not suite.tasks:
        return "n/a"
    steps = sorted({t.max_steps for t in suite.tasks})
    tools = sorted({name for t in suite.tasks for name in (t.allowed_tools or ["<all>"])})
    return f"max steps {'/'.join(map(str, steps))}; tools {', '.join(tools)}"


# ---------- single suite report -----------------------------------------------

def format_report(suite: SuiteResult, metrics: SuiteMetrics | None = None) -> str:
    m = metrics or compute_metrics(suite)
    c = suite.config
    lines = [
        f"Suite      : {suite.suite_name} ({len(suite.task_ids)} tasks x {suite.repeats} repeat(s) "
        f"= {m.scheduled_runs} scheduled runs)",
        f"Suite id   : {suite.suite_id}  (started {suite.started_at:%Y-%m-%d %H:%M} UTC)",
        f"Agent      : {agent_kind(suite)}",
        f"Config     : {c.name}  [provider {c.provider}, model {c.model}, prompt {c.prompt_hash}, "
        f"max attempts {c.max_attempts}]",
        f"Settings   : {_tools_summary(suite)}; dataset {suite.dataset or 'n/a'}",
        "",
    ]
    if m.complete:
        lines.append("Status     : COMPLETE - every scheduled run was executed and evaluated")
    else:
        lines.append(f"Status     : INCOMPLETE - {m.infra_errors} infrastructure error(s), "
                     f"{m.skipped_runs} skipped; results below cover {m.eligible_runs} of "
                     f"{m.scheduled_runs} scheduled runs")
    if suite.stop_reason:
        lines.append(f"Stopped    : {suite.stop_reason}")
    if suite.request_budget is not None or suite.estimated_requests is not None:
        lines.append(f"Requests   : {m.total_llm_calls} actual | estimate {suite.estimated_requests} | "
                     f"budget {suite.request_budget or 'none'}")
    levels = " | ".join(f"{level} {rate}" for level, rate in m.by_difficulty.items())
    lines += [
        f"Pass rate  : {m.pass_rate}   (passed / eligible runs)",
        f"By level   : {levels or 'n/a'}",
    ]
    if m.pass_at_k is not None:
        lines.append(f"Repeats    : pass@{m.k} {m.pass_at_k}  |  pass^{m.k} {m.pass_pow_k}")
    lines += [
        f"Avg steps  : {_num(m.avg_steps)}      Avg LLM calls: {_num(m.avg_llm_calls)}",
        f"Avg tokens : {_num(m.avg_input_tokens, '.0f')} in / {_num(m.avg_output_tokens, '.0f')} out",
        f"Time       : {_num(m.avg_duration_seconds, '.2f')} s avg, {m.total_duration_seconds:.2f} s total; "
        f"{m.total_llm_calls} LLM requests in total",
        f"Tool calls : {m.tool_calls} ({m.tool_errors} errors)",
        "Top failed : " + (", ".join(f"{name} x{n}" for name, n in m.failed_checks) or "none"),
        "",
        "Task       Level   Result",
    ]
    for record in suite.records:
        failed = [ch.name for ch in record.evaluation.checks if not ch.passed] if record.evaluation else []
        detail = (f"({record.run.error_kind}: not counted)" if record.outcome == "infra_error"
                  else f"({', '.join(failed)})" if failed else "")
        rep = f" #{record.repeat + 1}" if suite.repeats > 1 else ""
        lines.append(f"{record.task_id + rep:10} {record.difficulty or '-':7} {record.outcome.upper():11} {detail}")
    for skipped in suite.skipped:
        lines.append(f"{skipped.task_id:10} {'-':7} {'SKIPPED':11} ({skipped.reason})")
    lines += ["", format_failures(suite)]
    return "\n".join(lines)


# ---------- failure analysis (Phase 8) ----------------------------------------------

def _run_label(run: RunAnalysis, repeats: int) -> str:
    return run.task_id + (f" #{run.repeat + 1}" if repeats > 1 else "")


def format_failures(suite: SuiteResult, *, detailed: bool = False) -> str:
    """The failure-analysis section: categories with evidence, near misses, infra errors apart.

    detailed=False: counts + one example per category (for the normal report).
    detailed=True : every failed run with all its signals, and every warning (results.py failures).
    """
    title = "Failure analysis (rule-based, from the stored trace: likely patterns, not the model's reasoning)"
    if not suite.tasks:
        return f"{title}\n  not available: this result has no task definitions"
    a = analyze_suite(suite)
    lines = [title, f"  Failed runs : {a.failed_runs} of {a.failed_runs + a.passed_runs} evaluated"]
    for category, count in a.category_counts.items():
        examples = a.examples(category, limit=None if detailed else 1)
        lines.append(f"    {category:24} {count:>3}" + ("" if detailed else
                     f"   e.g. {_run_label(examples[0], suite.repeats)}: {examples[0].primary.evidence}"))
        if detailed:
            for run in examples:
                lines.append(f"      {_run_label(run, suite.repeats):12} {run.primary.evidence}")
                for signal in run.additional_signals:
                    lines.append(f"      {'':12}   also: {signal.name} - {signal.evidence}")
    kinds = Counter(r.infra_error_kind for r in a.runs if r.outcome == "infra_error")
    lines.append(f"  Infra errors: {a.infra_errors}" + (
        " (not agent failures: " + ", ".join(f"{k} x{n}" for k, n in kinds.items()) + ")" if kinds else ""))
    lines.append(f"  Skipped     : {a.skipped_runs}")
    if a.warning_counts:
        lines.append("  Near misses : " + ", ".join(f"{name} x{n}" for name, n in a.warning_counts.items())
                     + "  (warnings only; they never change pass/fail)")
        if detailed:
            for run in a.runs:
                for w in run.warnings:
                    lines.append(f"      {_run_label(run, suite.repeats):12} {w.name}: {w.evidence}")
    else:
        lines.append("  Near misses : none")
    if a.retries_not_recorded:
        lines.append(f"  Retries     : not recorded for {a.retries_not_recorded} run(s) (stored before retries "
                     f"were captured; unknown, not zero)")
    return "\n".join(lines)


# ---------- comparison -----------------------------------------------------------

def compare(suites: list[SuiteResult]) -> str:
    if len(suites) < 2:
        raise ValueError("compare needs at least two suite results")
    names = [s.config.name for s in suites]
    metrics = [compute_metrics(s) for s in suites]
    dimension_values = [str(get(s)) for get in {**CONFIG_DIMENSIONS, **FAIRNESS_DIMENSIONS}.values()
                        for s in suites]
    width = max(16, *(len(v) for v in names + dimension_values)) + 2   # every value fits its column

    def row(label: str, values: list[str]) -> str:
        return f"{label:30}" + "".join(f"{v:>{width}}" for v in values)

    lines = [row("", names), row("kind", ["SCRIPTED" if s.config.is_scripted else "REAL LLM" for s in suites])]
    for label, get in {**CONFIG_DIMENSIONS, **FAIRNESS_DIMENSIONS}.items():
        lines.append(row(label, [str(get(s)) for s in suites]))
    lines.append("")
    lines += [
        row("pass rate", [str(m.pass_rate) for m in metrics]),
        *[row(f"  {level}", [str(m.by_difficulty.get(level, '-')) for m in metrics])
          for level in ("easy", "medium", "hard") if any(level in m.by_difficulty for m in metrics)],
        row("avg steps", [_num(m.avg_steps) for m in metrics]),
        row("avg LLM calls", [_num(m.avg_llm_calls) for m in metrics]),
        row("avg input tokens", [_num(m.avg_input_tokens, ".0f") for m in metrics]),
        row("avg time (s)", [_num(m.avg_duration_seconds, ".2f") for m in metrics]),
        row("tool errors", [str(m.tool_errors) for m in metrics]),
        row("infra errors", [str(m.infra_errors) for m in metrics]),
        row("complete", ["yes" if m.complete else "NO" for m in metrics]),
        "",
    ]

    # Per-task outcomes side by side (first repeat shown when repeated).
    outcome = [{(r.task_id, r.repeat): r.outcome for r in s.records} for s in suites]
    for task_id in suites[0].task_ids:
        values = [o.get((task_id, 0), "skipped") for o in outcome]
        marker = "  <- differs" if len(set(values)) > 1 else ""
        lines.append(row(task_id, values) + marker)
    lines.append("")

    # Honest conclusions about what the comparison can and cannot show.
    unfair = [label for label, get in FAIRNESS_DIMENSIONS.items() if len({str(get(s)) for s in suites}) > 1]
    changed = [label for label, get in CONFIG_DIMENSIONS.items() if len({str(get(s)) for s in suites}) > 1]
    if unfair:
        lines.append("NOT A FAIR COMPARISON: these differ between runs: " + ", ".join(unfair)
                     + ". Results are not comparable.")
    if any(not m.complete for m in metrics):
        lines.append("WARNING: at least one run is INCOMPLETE; compare pass rates with their denominators.")
    if unfair:
        # Not comparable: list what changed for information, but never explain the differences.
        lines.append("Configuration: " + ("no dimension changed either; the difference is in how the runs "
                                          "were set up (above), so no conclusion about the agent is possible."
                                          if not changed else "also changed: " + ", ".join(changed) + "."))
    elif not changed:
        lines.append("No configuration dimension changed: differences reflect run-to-run variation only.")
    elif len(changed) == 1:
        lines.append(f"Changed dimension: {changed[0]} (the only configuration difference).")
    else:
        lines.append("WARNING: several dimensions changed (" + ", ".join(changed) + "); "
                     "differences cannot be attributed to any single one of them.")
    if any(s.config.is_scripted for s in suites):
        lines.append("NOTE: scripted agents only test the framework; their scores say nothing about AI ability.")
    return "\n".join(lines)


# ---------- JSON export -----------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "x"


def export_json(suite: SuiteResult, directory: str | Path = RESULTS_DIR) -> Path:
    """Write the full suite result (every run, trace, check, timestamp, config) + metrics.

    Never overwrites: the name includes a timestamp, and the file is created with mode "x".
    If that name is already taken (two exports within the same clock tick), "_2", "_3", ...
    is added instead of failing.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = f"{_slug(suite.suite_name)}_{_slug(suite.config.name)}_{stamp}"
    payload = {
        "format": EXPORT_FORMAT,
        "suite_result": json.loads(suite.model_dump_json()),
        "metrics": json.loads(compute_metrics(suite).model_dump_json()),  # derived, for convenience
        "tasks_fingerprint": suite.tasks_fingerprint,
    }
    for attempt in range(1, 1000):
        path = directory / (f"{base}.json" if attempt == 1 else f"{base}_{attempt}.json")
        try:
            with open(path, "x", encoding="utf-8") as f:  # "x" = create only, never overwrite
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return path
        except FileExistsError:
            continue  # taken: try the next suffix
    raise FileExistsError(f"could not find a free file name for {base}.json in {directory}")


def load_json(path: str | Path) -> SuiteResult:
    """Load an exported suite result back (validated again). Metrics are recomputed, not trusted."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != EXPORT_FORMAT:
        raise ValueError(f"not an AgentBench suite result: format={payload.get('format')!r}")
    return SuiteResult.model_validate(payload["suite_result"])

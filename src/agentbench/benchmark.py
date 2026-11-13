"""Suite runner: run every task of a suite (x repeats), evaluate, keep EVERY result.

    for each task, for each repeat (sequentially - never in parallel):
        run = AgentRunner(...).run(task)              # execution (Phase 4)
        if run is an infrastructure error:            # not the agent's fault
            record it as "infra_error", no evaluation
        else:
            evaluation = evaluate(task, run)          # evaluation (Phase 5)
            record it as "passed" / "failed"

Nothing is discarded: every scheduled run ends up as a RunRecord or a SkippedRun.
"""

import time
from collections.abc import Callable

from agentbench.evaluators import evaluate
from agentbench.llm.base import LLMClient
from agentbench.models import AgentConfig, RunRecord, SuiteResult, Task, _utc_now, is_infra_error
from agentbench.runner import AgentRunner, RetryPolicy
from agentbench.tools.registry import ToolRegistry

# Builds the LLM for one run. Gets (task, repeat) so a scripted FakeLLM can be created
# per task; a real client (Gemini) can simply return the same object every time.
LLMFactory = Callable[[Task, int], LLMClient]


def run_suite(
    tasks: list[Task],
    config: AgentConfig,
    make_llm: LLMFactory,
    tools: ToolRegistry,
    *,
    suite_name: str,
    repeats: int = 1,
    dataset: str | None = None,
    progress: Callable[[str], None] | None = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.perf_counter,
) -> SuiteResult:
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError(f"task ids must be unique: {ids}")
    say = progress or (lambda _message: None)

    suite = SuiteResult(suite_name=suite_name, config=config, task_ids=ids, repeats=repeats,
                        tasks=tasks, dataset=dataset)
    total, done = len(tasks) * repeats, 0
    for task in tasks:
        for repeat in range(repeats):
            done += 1
            label = f"[{done}/{total}] {task.id}" + (f" (repeat {repeat + 1}/{repeats})" if repeats > 1 else "")
            runner = AgentRunner(
                make_llm(task, repeat), tools,
                system_prompt=config.system_prompt,
                retry=RetryPolicy(max_attempts=config.max_attempts),
                sleep=sleep, clock=clock,
            )
            run = runner.run(task)
            if is_infra_error(run):
                record = RunRecord(task_id=task.id, repeat=repeat, difficulty=task.difficulty,
                                   run=run, outcome="infra_error")
                say(f"{label}: INFRA ERROR ({run.error_kind}) - not counted as an agent failure")
            else:
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

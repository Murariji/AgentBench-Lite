"""Suite runner tests with FakeLLM: no internet, no quota, no real waiting."""

import pytest

from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.benchmark import run_suite
from agentbench.metrics import compute_metrics
from agentbench.models import AgentConfig, SuiteResult, Task
from agentbench.suites import SHOP_TASKS
from agentbench.tools import CalculatorTool, ToolRegistry

CONFIG = AgentConfig(name="scripted", provider="fake", model="scripted-v1", system_prompt="be careful")
TASKS = [
    Task(id="add", prompt="2+2?", expected_answer="4", answer_type="number", difficulty="easy"),
    Task(id="mul", prompt="6*7?", expected_answer="42", answer_type="number", difficulty="hard"),
]


def solve(expression: str, answer: str) -> FakeLLM:
    return FakeLLM([
        LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": expression})),
        LLMResponse(text=answer),
    ])


def run(tasks, make_llm, repeats=1):
    messages: list[str] = []
    result = run_suite(tasks, CONFIG, make_llm, ToolRegistry([CalculatorTool()]), suite_name="math",
                       repeats=repeats, progress=messages.append, sleep=lambda s: None)
    return result, messages


def test_runs_every_task_and_evaluates_each_run():
    answers = {"add": ("2+2", "4"), "mul": ("6*7", "41")}              # mul answered wrong
    result, messages = run(TASKS, lambda task, repeat: solve(*answers[task.id]))
    assert [r.outcome for r in result.records] == ["passed", "failed"]
    assert all(r.evaluation.run_id == r.run.run_id for r in result.records)  # linked
    assert result.is_complete and result.finished_at is not None
    assert messages[0].startswith("[1/2] add: PASSED")
    assert "failed: answer:number" in messages[1]


def test_infra_errors_are_recorded_not_evaluated():
    def make_llm(task, repeat):
        if task.id == "mul":
            return FakeLLM([LLMError("daily quota used up", kind="quota_exhausted", status_code=429)])
        return solve("2+2", "4")

    result, messages = run(TASKS, make_llm)
    infra = result.records[1]
    assert infra.outcome == "infra_error" and infra.evaluation is None
    assert infra.run.error_kind == "quota_exhausted"                  # nothing silently discarded
    assert "INFRA ERROR (quota_exhausted)" in messages[1]
    assert not result.is_complete and messages[-1].startswith("Suite INCOMPLETE")
    m = compute_metrics(result)
    assert str(m.pass_rate) == "1/1 (100.0%)" and m.infra_errors == 1


def test_unusable_model_reply_is_an_agent_failure_not_infra():
    result, _ = run(TASKS[:1], lambda t, r: FakeLLM([LLMError("empty reply", kind="invalid_response")]))
    assert result.records[0].outcome == "failed"                      # the MODEL failed


def test_retries_happen_inside_a_run():
    def make_llm(task, repeat):
        return FakeLLM([LLMError("busy", kind="server", status_code=503),
                        *solve("2+2", "4")._responses])
    result, _ = run(TASKS[:1], make_llm)
    assert result.records[0].outcome == "passed" and result.records[0].run.llm_calls == 3


def test_repeats_create_one_record_each_and_pass_at_k():
    flaky = {0: ("2+2", "4"), 1: ("2+2", "5")}                        # passes once, fails once
    result, messages = run(TASKS[:1], lambda task, repeat: solve(*flaky[repeat]), repeats=2)
    assert [(r.repeat, r.outcome) for r in result.records] == [(0, "passed"), (1, "failed")]
    assert "(repeat 2/2)" in messages[1]
    m = compute_metrics(result)
    assert str(m.pass_at_k) == "1/1 (100.0%)" and str(m.pass_pow_k) == "0/1 (0.0%)"


def test_duplicate_task_ids_are_rejected():
    with pytest.raises(ValueError):
        run([TASKS[0], TASKS[0]], lambda t, r: solve("2+2", "4"))


def test_suite_result_round_trips_through_json():
    result, _ = run(TASKS, lambda task, repeat: solve("2+2", "4"))
    restored = SuiteResult.model_validate_json(result.model_dump_json())
    assert restored == result and restored.config.prompt_hash == CONFIG.prompt_hash


def test_shop_tasks_have_explicit_difficulties():
    levels = [t.difficulty for t in SHOP_TASKS]
    assert (levels.count("easy"), levels.count("medium"), levels.count("hard")) == (2, 4, 4)

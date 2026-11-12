"""Tests for evaluators. Hand-made RunResults: no agent, no LLM, no API calls."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from agentbench.evaluators import (
    check_contains,
    check_exact,
    check_number,
    evaluate,
    extract_number,
    normalize_text,
)
from agentbench.llm import FakeLLM, LLMResponse, ToolRequest
from agentbench.models import Check, EvaluationResult, RunResult, Step, Task, ToolCall, Trace
from agentbench.runner import AgentRunner
from agentbench.tools import CalculatorTool, ToolRegistry


# ---------- helpers ----------------------------------------------------------

def make_result(answer, status="completed", calls=(), task_id="t1", **extra) -> RunResult:
    """A RunResult written by hand. `calls` = ToolCalls, one per step."""
    steps = [Step(index=i, llm_output="", tool_call=c) for i, c in enumerate(calls)]
    if answer is not None:
        steps.append(Step(index=len(steps), llm_output=answer))
    return RunResult(task_id=task_id, status=status, final_answer=answer,
                     trace=Trace(task_id=task_id, steps=steps), duration_seconds=0.1, **extra)


CALC_OK = ToolCall(tool_name="calculator", arguments={"expression": "0.15*840"}, output="126")
CALC_ERR = ToolCall(tool_name="calculator", arguments={"expression": "15% of 840"}, error="unsupported syntax")
NUMBER_TASK = Task(id="t1", prompt="What is 15% of 840?", expected_answer="126",
                   answer_type="number", required_tools=["calculator"])


# ---------- the example table from the lesson --------------------------------

@pytest.mark.parametrize(
    "result, verdict, failing",
    [
        (make_result("126", calls=[CALC_OK]), True, []),
        (make_result("15% of 840 is 126.", calls=[CALC_OK]), True, []),
        (make_result("126"), False, ["required_tools"]),                       # guessed
        (make_result("120 or 126", calls=[CALC_OK]), False, ["answer:number"]),  # ambiguous
        (make_result(None, status="max_steps", calls=[CALC_ERR] * 3), False,
         ["status", "answer:number", "required_tools"]),
    ],
)
def test_lesson_examples(result, verdict, failing):
    evaluation = evaluate(NUMBER_TASK, result)
    assert evaluation.passed is verdict
    assert [c.name for c in evaluation.checks if not c.passed] == failing
    assert all(c.reason for c in evaluation.checks)        # every check explains itself


def test_evaluation_links_to_the_run():
    result = make_result("126", calls=[CALC_OK])
    evaluation = evaluate(NUMBER_TASK, result)
    assert evaluation.run_id == result.run_id and evaluation.task_id == "t1"


# ---------- number extraction ------------------------------------------------

@pytest.mark.parametrize(
    "answer, expected",
    [
        ("126", "126"),
        ("126.0", "126"),
        ("15% of 840 is 126.", "126"),
        ("₹1,240", "1240"),
        ("Rs. 1,240.00", "1240"),
        ("Rs.1,240", "1240"),
        ("$1240", "1240"),
        ("INR 1,240", "1240"),
        ("1240 rupees", "1240"),
        ("12,40,000", "1240000"),        # Indian grouping
        ("1,240,000", "1240000"),        # Western grouping
        ("-12.5", "-12.5"),
        ("12.5%", "12.5"),
        ("Total: 3,500", "3500"),
        ("Q1 orders: 1,200", "1200"),    # the 1 in "Q1" is not a number
        ("126 and again 126", "126"),    # all numbers the same
        ("Revenue was 1,200 in Jan and 1,500 in Feb, so growth is 25%", "25"),
    ],
)
def test_extract_number_reads_formats(answer, expected):
    assert extract_number(answer).value == Decimal(expected)


@pytest.mark.parametrize(
    "answer, reason_part",
    [
        ("no idea", "no number found"),
        ("1,5", "unclear number format"),     # European decimal? we refuse to guess
        ("9,99", "unclear number format"),
        ("120 or 126", "ambiguous"),
        ("between 120 and 130", "ambiguous"),
    ],
)
def test_extract_number_refuses_when_unsure(answer, reason_part):
    parsed = extract_number(answer)
    assert parsed.value is None and reason_part in parsed.reason


def test_decimal_avoids_float_surprises():
    assert 0.1 + 0.2 != 0.3                                   # the float problem
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")  # Decimal is exact
    assert check_number("126", "126.00000000000001").passed is False   # exact by default
    assert check_number("126", "126.00000000000001", abs_tol=1e-9).passed is True


def test_tolerances():
    assert check_number("33.3333", "33.33", rel_tol=0.001).passed is True
    assert check_number("33.3333", "33.33", rel_tol=0.00001).passed is False
    assert check_number("1240", "1240.004", abs_tol=0.01).passed is True
    failed = check_number("126", "130")
    assert not failed.passed and "expected 126" in failed.reason and "difference 4" in failed.reason


def test_unclear_expected_answer_is_reported():
    check = check_number("about a hundred", "100")
    assert not check.passed and "not one clear number" in check.reason


# ---------- exact / contains -------------------------------------------------

def test_normalize_text():
    assert normalize_text('  "Paris."  ') == "paris"
    assert normalize_text("New   Delhi!") == "new delhi"


def test_exact_match():
    assert check_exact("Paris", ' paris. ').passed
    assert not check_exact("Paris", "Paris, France").passed


def test_contains_matches_whole_words_only():
    assert check_contains("Delhi", "The city is Delhi.").passed
    assert not check_contains("Delhi", "Delhiwala Stores").passed


def test_contains_limitation_is_documented():
    # KNOWN LIMITATION: text matching can't understand negation.
    assert check_contains("Delhi", "Not Delhi, it's Mumbai").passed


# ---------- status, required tools, missing data -----------------------------

def test_status_reasons():
    max_steps = evaluate(NUMBER_TASK, make_result(None, status="max_steps"))
    assert "step limit" in max_steps.checks[0].reason
    error = evaluate(NUMBER_TASK, make_result(None, status="error", error="daily quota used up",
                                              error_kind="quota_exhausted"))
    assert "quota_exhausted" in error.checks[0].reason


def test_required_tool_called_but_always_failing():
    evaluation = evaluate(NUMBER_TASK, make_result("126", calls=[CALC_ERR, CALC_ERR]))
    tools = evaluation.checks[-1]
    assert not tools.passed and "called 2 time(s) but never succeeded" in tools.reason


def test_no_required_tools_means_no_tool_check():
    task = Task(id="t1", prompt="Capital of France?", expected_answer="Paris")
    evaluation = evaluate(task, make_result("Paris"))
    assert [c.name for c in evaluation.checks] == ["status", "answer:exact"]
    assert evaluation.passed


def test_task_without_expected_answer_cannot_pass():
    task = Task(id="t1", prompt="Write a poem")
    evaluation = evaluate(task, make_result("Roses are red"))
    assert not evaluation.passed and "cannot be graded" in evaluation.checks[1].reason


def test_mismatched_task_and_result_is_a_programming_error():
    with pytest.raises(ValueError):
        evaluate(NUMBER_TASK, make_result("126", task_id="other"))


# ---------- the models -------------------------------------------------------

def test_verdict_can_never_disagree_with_checks():
    failing = [Check(name="status", passed=False, reason="max_steps")]
    with pytest.raises(ValidationError):
        EvaluationResult(run_id="r", task_id="t", passed=True, checks=failing)


def test_task_grading_fields_are_validated():
    with pytest.raises(ValidationError):
        Task(id="t", prompt="p", abs_tolerance=-1)
    with pytest.raises(ValidationError):
        Task(id="t", prompt="p", answer_type="fuzzy")


def test_run_ids_are_unique_and_evaluation_round_trips():
    a, b = make_result("126", calls=[CALC_OK]), make_result("126", calls=[CALC_OK])
    assert a.run_id != b.run_id
    evaluation = evaluate(NUMBER_TASK, a)
    assert EvaluationResult.model_validate_json(evaluation.model_dump_json()) == evaluation


# ---------- execution + evaluation together ----------------------------------

def test_runner_then_evaluator_pipeline():
    llm = FakeLLM([
        LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": "0.15 * 840"})),
        LLMResponse(text="15% of 840 is 126."),
    ])
    result = AgentRunner(llm, ToolRegistry([CalculatorTool()])).run(NUMBER_TASK)  # execution
    evaluation = evaluate(NUMBER_TASK, result)                                    # evaluation
    assert result.status == "completed" and evaluation.passed
    assert evaluation.run_id == result.run_id

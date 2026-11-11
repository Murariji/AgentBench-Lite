"""Tests for the core data models: good data is accepted, bad data is rejected."""

import pytest
from pydantic import ValidationError

from agentbench.models import RunResult, Step, Task, ToolCall, Trace


# ---------- helpers ----------------------------------------------------------

def make_trace() -> Trace:
    """A small realistic trace: one tool call, then a final answer."""
    return Trace(
        task_id="math-001",
        steps=[
            Step(
                index=0,
                llm_output="I should use the calculator.",
                tool_call=ToolCall(
                    tool_name="calculator",
                    arguments={"expression": "2+2"},
                    output="4",
                ),
            ),
            Step(index=1, llm_output="The answer is 4."),
        ],
    )


# ---------- Task -------------------------------------------------------------

def test_task_valid_with_defaults():
    task = Task(id="math-001", prompt="What is 2+2?")
    assert task.expected_answer is None
    assert task.allowed_tools == []
    assert task.max_steps == 10


@pytest.mark.parametrize("bad_max_steps", [0, -1])
def test_task_rejects_non_positive_max_steps(bad_max_steps):
    with pytest.raises(ValidationError):
        Task(id="t", prompt="p", max_steps=bad_max_steps)


def test_task_rejects_missing_prompt():
    with pytest.raises(ValidationError):
        Task(id="t")


def test_task_rejects_unknown_field():
    # extra="forbid" catches typos like 'promt'
    with pytest.raises(ValidationError):
        Task(id="t", prompt="p", promt="typo")


# ---------- ToolCall ---------------------------------------------------------

def test_toolcall_with_output_error_or_neither():
    ok = ToolCall(tool_name="calculator", arguments={"expression": "1+1"}, output="2")
    failed = ToolCall(tool_name="calculator", error="division by zero")
    pending = ToolCall(tool_name="calculator")
    assert ok.output == "2" and ok.error is None
    assert failed.error == "division by zero" and failed.output is None
    assert pending.output is None and pending.error is None


def test_toolcall_rejects_both_output_and_error():
    with pytest.raises(ValidationError):
        ToolCall(tool_name="calculator", output="2", error="boom")


# ---------- Step / Trace -----------------------------------------------------

def test_step_gets_timezone_aware_timestamp():
    step = Step(index=0, llm_output="hi")
    assert step.timestamp.tzinfo is not None


def test_trace_keeps_steps_in_order():
    trace = make_trace()
    assert [s.index for s in trace.steps] == [0, 1]


def test_trace_rejects_out_of_order_steps():
    with pytest.raises(ValidationError):
        Trace(
            task_id="t",
            steps=[Step(index=1, llm_output="a"), Step(index=0, llm_output="b")],
        )


# ---------- RunResult --------------------------------------------------------

def test_runresult_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RunResult(task_id="t", status="done", trace=Trace(task_id="t"), duration_seconds=1.0)


def test_runresult_json_round_trip():
    # Proves results can be saved (Phase 7) and sent over an API (Phase 9).
    original = RunResult(
        task_id="math-001",
        status="success",
        final_answer="4",
        trace=make_trace(),
        duration_seconds=0.42,
    )
    json_text = original.model_dump_json()
    restored = RunResult.model_validate_json(json_text)
    assert restored == original

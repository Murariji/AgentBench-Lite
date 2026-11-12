"""Tests for the agent loop. FakeLLM only: no internet, no key, no quota, no real waiting."""

import pytest

from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.models import RunResult, Task
from agentbench.runner import AgentRunner, RetryPolicy
from agentbench.tools import CalculatorTool, LookupTool, ToolRegistry, WordCountTool


# ---------- helpers ----------------------------------------------------------

def tool(name: str, **arguments) -> LLMResponse:
    """A scripted reply where the model ASKS for a tool."""
    return LLMResponse(tool_request=ToolRequest(name=name, arguments=arguments))


def say(text: str, **tokens) -> LLMResponse:
    """A scripted reply with a final text answer."""
    return LLMResponse(text=text, **tokens)


class FakeSleep:
    """Records how long the runner WANTED to wait, without actually waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry([CalculatorTool(), WordCountTool(), LookupTool({"capital of france": "Paris"})])


def run(registry, script, task=None, **runner_args):
    """Run one task with a FakeLLM; return (result, llm, sleep) for inspection."""
    llm = FakeLLM(script)
    sleep = FakeSleep()
    runner = AgentRunner(llm, registry, sleep=sleep, **runner_args)
    result = runner.run(task or Task(id="t1", prompt="What is 15% of 840?"))
    return result, llm, sleep


# ---------- the happy paths --------------------------------------------------

def test_tool_then_answer_completes(registry):
    result, llm, _ = run(registry, [tool("calculator", expression="0.15 * 840"), say("126")])

    assert result.status == "completed" and result.final_answer == "126"
    assert len(result.trace.steps) == 2 and result.llm_calls == 2
    assert result.trace.steps[0].tool_call.output == "126"   # OUR tool ran
    # The 2nd request contained the whole history: question, tool request, tool result.
    second = llm.calls[1].messages
    assert [m.role for m in second] == ["user", "assistant", "tool"]
    assert second[2].text == "126" and not second[2].is_error


def test_direct_answer_without_tools(registry):
    result, _, _ = run(registry, [say("Hello")])
    assert result.status == "completed" and result.final_answer == "Hello"
    assert result.trace.steps[0].tool_call is None


def test_multi_tool_task(registry):
    task = Task(id="t2", prompt="15% of 840 plus the words in 'the quick brown fox'?")
    script = [
        tool("calculator", expression="0.15*840"),
        tool("word_count", text="the quick brown fox"),
        tool("calculator", expression="126+4"),
        say("130"),
    ]
    result, _, _ = run(registry, script, task)
    assert result.final_answer == "130"
    assert [s.tool_call.output for s in result.trace.steps[:3]] == ["126", "4", "130"]


def test_tokens_are_recorded_per_step(registry):
    result, _, _ = run(registry, [say("4", input_tokens=200, output_tokens=5)])
    step = result.trace.steps[0]
    assert (step.input_tokens, step.output_tokens) == (200, 5)


def test_result_is_json_round_trippable(registry):
    result, _, _ = run(registry, [tool("calculator", expression="2+2"), say("4")])
    assert RunResult.model_validate_json(result.model_dump_json()) == result


# ---------- stopping and tool problems ---------------------------------------

def test_step_limit_stops_the_loop_without_extra_calls(registry):
    task = Task(id="loop", prompt="?", max_steps=3)
    result, llm, _ = run(registry, [tool("calculator", expression="1+1")] * 5, task)
    assert result.status == "max_steps" and result.final_answer is None
    assert len(result.trace.steps) == 3 and result.llm_calls == 3
    assert llm.remaining == 2  # the loop never asked for more than allowed


def test_tool_error_is_fed_back_and_agent_recovers(registry):
    script = [tool("calculator", expression="1/0"), tool("calculator", expression="2+2"), say("4")]
    result, llm, _ = run(registry, script)
    assert result.status == "completed"
    assert "division by zero" in result.trace.steps[0].tool_call.error
    feedback = llm.calls[1].messages[-1]
    assert feedback.role == "tool" and feedback.is_error


def test_empty_allowed_tools_means_no_tools(registry):
    task = Task(id="t", prompt="2+2?", allowed_tools=[])
    result, llm, _ = run(registry, [tool("calculator", expression="2+2"), say("4")], task)
    assert llm.calls[0].tool_names == []                        # no tool menu offered
    assert "not allowed" in result.trace.steps[0].tool_call.error
    assert result.status == "completed"


def test_allowed_tools_list_limits_the_menu(registry):
    task = Task(id="t", prompt="capital?", allowed_tools=["lookup"])
    _, llm, _ = run(registry, [say("Paris")], task)
    assert llm.calls[0].tool_names == ["lookup"]


def test_unknown_allowed_tool_stops_before_any_api_call(registry):
    task = Task(id="t", prompt="?", allowed_tools=["teleport"])
    result, llm, _ = run(registry, [say("never used")], task)
    assert result.status == "error" and result.error_kind == "config"
    assert result.llm_calls == 0 and llm.calls == []


# ---------- retries and quota policy -----------------------------------------

def test_503_is_retried_then_succeeds(registry):
    result, _, sleep = run(registry, [LLMError("busy", kind="server", status_code=503), say("ok")])
    assert result.status == "completed" and result.llm_calls == 2
    assert sleep.delays == [1.0]


def test_network_error_is_retried(registry):
    result, _, _ = run(registry, [LLMError("offline", kind="network"), say("ok")])
    assert result.status == "completed"


def test_retries_are_bounded_with_exponential_backoff(registry):
    script = [LLMError("busy", kind="server", status_code=503)] * 10
    result, llm, sleep = run(registry, script, retry=RetryPolicy(max_attempts=3))
    assert result.status == "error" and result.error_kind == "server"
    assert result.llm_calls == 3 and len(llm.calls) == 3   # never more than max_attempts
    assert sleep.delays == [1.0, 2.0]                      # 1s, then 2s
    assert "gave up after 3" in result.error


def test_401_stops_immediately(registry):
    result, llm, sleep = run(registry, [LLMError("bad key", kind="auth", status_code=401), say("x")])
    assert result.status == "error" and result.error_kind == "auth"
    assert result.llm_calls == 1 and sleep.delays == [] and llm.remaining == 1


def test_daily_quota_is_a_hard_stop(registry):
    quota = LLMError("daily quota used up", kind="quota_exhausted", status_code=429)
    result, llm, sleep = run(registry, [quota, say("x")])
    assert result.status == "error" and result.error_kind == "quota_exhausted"
    assert result.llm_calls == 1 and sleep.delays == [] and llm.remaining == 1


def test_rate_limit_respects_retry_after(registry):
    limit = LLMError("per-minute limit", kind="rate_limit", status_code=429, retry_after=5.0)
    result, _, sleep = run(registry, [limit, say("ok")])
    assert result.status == "completed" and sleep.delays == [5.0]


def test_too_long_retry_after_stops_instead_of_waiting(registry):
    limit = LLMError("wait 10 min", kind="rate_limit", status_code=429, retry_after=600.0)
    result, _, sleep = run(registry, [limit, say("ok")])
    assert result.status == "error" and result.llm_calls == 1 and sleep.delays == []


def test_bug_in_llm_client_becomes_error_result(registry):
    class BrokenLLM(FakeLLM):
        def generate(self, messages, tools, system_prompt=None):
            raise RuntimeError("oops")

    result = AgentRunner(BrokenLLM([]), registry).run(Task(id="t", prompt="?"))
    assert result.status == "error" and result.error_kind == "unknown" and "oops" in result.error


def test_retry_policy_rejects_invalid_settings():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-1)

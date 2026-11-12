"""Tests for the LLM layer. No internet and no API key needed."""

import pytest
from pydantic import ValidationError

from agentbench.llm import FakeLLM, LLMClient, LLMError, LLMResponse, Message, ToolRequest
from agentbench.models import Step
from agentbench.tools import CalculatorTool


# ---------- data shapes ------------------------------------------------------

def test_message_rules_per_role():
    Message(role="user", text="hi")
    Message(role="assistant", tool_request=ToolRequest(name="calculator"))
    Message(role="tool", tool_request=ToolRequest(name="calculator"), text="4")
    with pytest.raises(ValidationError):
        Message(role="user")                      # user needs text
    with pytest.raises(ValidationError):
        Message(role="assistant")                 # needs text or tool_request
    with pytest.raises(ValidationError):
        Message(role="tool", text="4")            # must say which request it answers
    with pytest.raises(ValidationError):
        Message(role="robot", text="hi")          # unknown role


def test_llmresponse_needs_text_or_tool_request():
    with pytest.raises(ValidationError):
        LLMResponse()
    reply = LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": "1+1"}))
    msg = reply.to_message()
    assert msg.role == "assistant" and msg.tool_request.name == "calculator"


def test_step_records_tokens_and_rejects_negative():
    step = Step(index=0, llm_output="hi", input_tokens=12, output_tokens=3)
    assert (step.input_tokens, step.output_tokens) == (12, 3)
    assert Step(index=0, llm_output="hi").input_tokens is None
    with pytest.raises(ValidationError):
        Step(index=0, llm_output="hi", input_tokens=-1)


# ---------- FakeLLM ----------------------------------------------------------

def test_fake_llm_replies_in_order_and_records_calls():
    script = [
        LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": "2+2"})),
        LLMResponse(text="The answer is 4."),
    ]
    llm = FakeLLM(script)
    assert isinstance(llm, LLMClient)

    history = [Message(role="user", text="What is 2+2?")]
    first = llm.generate(history, [CalculatorTool()], system_prompt="be careful")
    second = llm.generate(history, [CalculatorTool()])

    assert first.tool_request.name == "calculator"
    assert second.text == "The answer is 4."
    assert len(llm.calls) == 2
    assert llm.calls[0].tool_names == ["calculator"]
    assert llm.calls[0].system_prompt == "be careful"
    assert len(script) == 2  # the caller's list was not modified


def test_fake_llm_raises_when_script_runs_out():
    llm = FakeLLM([])
    with pytest.raises(LLMError):
        llm.generate([Message(role="user", text="hi")], [])

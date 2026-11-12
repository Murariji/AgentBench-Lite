"""Tests for the Gemini translation code. Needs the Gemini SDK installed, but NO network or key.

If the SDK is missing, pytest skips this whole file (instead of failing).
"""

import pytest

from agentbench.llm import LLMError, Message, ToolRequest
from agentbench.tools import CalculatorTool

types = pytest.importorskip("google.genai.types")
from agentbench.llm import gemini  # noqa: E402  (import only after the SDK check)


def test_tool_becomes_function_declaration():
    decl = gemini.tool_to_declaration(CalculatorTool())
    assert decl.name == "calculator"
    assert decl.parameters_json_schema["required"] == ["expression"]


def test_messages_translate_to_gemini_contents():
    request = ToolRequest(
        name="calculator",
        arguments={"expression": "2+2"},
        id="call-1",
        provider_data={"gemini_thought_signature": "c2lnbmF0dXJl"},  # base64 of b"signature"
    )
    contents = gemini.messages_to_contents([
        Message(role="user", text="What is 2+2?"),
        Message(role="assistant", tool_request=request),
        Message(role="tool", tool_request=request, text="4"),
    ])
    assert [c.role for c in contents] == ["user", "model", "user"]
    call_part = contents[1].parts[0]
    assert call_part.function_call.name == "calculator"
    assert call_part.thought_signature == b"signature"  # sent back unchanged
    result = contents[2].parts[0].function_response
    assert result.id == "call-1" and result.response == {"result": "4"}


def test_tool_error_is_sent_as_error():
    request = ToolRequest(name="calculator")
    contents = gemini.messages_to_contents(
        [Message(role="tool", tool_request=request, text="division by zero", is_error=True)]
    )
    assert contents[0].parts[0].function_response.response == {"error": "division by zero"}


def _fake_gemini_response(parts, prompt_tokens=10, out_tokens=5, thought_tokens=None):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens,
            candidates_token_count=out_tokens,
            thoughts_token_count=thought_tokens,
        ),
    )


def test_gemini_tool_call_response_is_translated():
    raw = _fake_gemini_response(
        [types.Part(
            function_call=types.FunctionCall(id="c1", name="calculator", args={"expression": "840*0.15"}),
            thought_signature=b"sig",
        )],
        thought_tokens=7,
    )
    reply = gemini.response_to_llm_response(raw)
    assert reply.tool_request.name == "calculator"
    assert reply.tool_request.arguments == {"expression": "840*0.15"}
    assert reply.tool_request.provider_data["gemini_thought_signature"] == "c2ln"  # base64 of b"sig"
    assert (reply.input_tokens, reply.output_tokens) == (10, 12)  # 5 answer + 7 thinking


def test_gemini_text_response_skips_thoughts():
    raw = _fake_gemini_response(
        [types.Part(text="secret reasoning", thought=True), types.Part(text="The answer is 126.")]
    )
    reply = gemini.response_to_llm_response(raw)
    assert reply.text == "The answer is 126." and reply.tool_request is None


def test_gemini_empty_response_raises_llm_error():
    with pytest.raises(LLMError):
        gemini.response_to_llm_response(_fake_gemini_response([]))


def test_gemini_client_without_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        gemini.GeminiClient()

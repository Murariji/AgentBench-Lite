"""GeminiClient: the only file in the project that knows about Google's SDK.

Its job is translation:
    our Message / Tool  --->  Gemini's request format
    Gemini's response   --->  our LLMResponse
"""

import base64
import os
from typing import Any

from agentbench.llm.base import LLMClient, LLMError, LLMResponse, Message, ToolRequest
from agentbench.tools.base import Tool

try:  # the SDK is an optional extra: pip install -e ".[gemini]"
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types
except ImportError:  # pragma: no cover - only hit when the extra is not installed
    genai = None

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # free-tier friendly; override with GEMINI_MODEL in .env
_SIGNATURE_KEY = "gemini_thought_signature"


def _require_sdk() -> None:
    if genai is None:
        raise LLMError('Gemini SDK not installed. Run: pip install -e ".[dev,gemini]"')


# ---------- translation: ours -> Gemini ---------------------------------------

def tool_to_declaration(tool: Tool) -> "types.FunctionDeclaration":
    """Our Tool's name/description/parameters become a Gemini 'function declaration'."""
    _require_sdk()
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters_json_schema=tool.parameters,
    )


def _function_call_part(request: ToolRequest) -> "types.Part":
    signature = request.provider_data.get(_SIGNATURE_KEY)
    return types.Part(
        function_call=types.FunctionCall(id=request.id, name=request.name, args=request.arguments),
        thought_signature=base64.b64decode(signature) if signature else None,
    )


def messages_to_contents(messages: list[Message]) -> list["types.Content"]:
    """Our conversation history -> Gemini's list of Content objects.

    Gemini uses role "model" (not "assistant"), and tool results are sent
    as a "function_response" part inside a "user" turn.
    """
    _require_sdk()
    contents: list[types.Content] = []
    for msg in messages:
        if msg.role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=msg.text)]))
        elif msg.role == "assistant":
            parts = []
            if msg.text:
                parts.append(types.Part(text=msg.text))
            if msg.tool_request:
                parts.append(_function_call_part(msg.tool_request))
            contents.append(types.Content(role="model", parts=parts))
        else:  # role == "tool"
            result_key = "error" if msg.is_error else "result"
            response = types.FunctionResponse(
                id=msg.tool_request.id,
                name=msg.tool_request.name,
                response={result_key: msg.text},
            )
            contents.append(types.Content(role="user", parts=[types.Part(function_response=response)]))
    return contents


# ---------- translation: Gemini -> ours ---------------------------------------

def response_to_llm_response(response: "types.GenerateContentResponse") -> LLMResponse:
    """Gemini's reply -> our LLMResponse (text and/or the FIRST tool request, + tokens)."""
    parts = []
    if response.candidates and response.candidates[0].content:
        parts = response.candidates[0].content.parts or []

    texts: list[str] = []
    tool_request: ToolRequest | None = None
    for part in parts:
        if part.thought:  # the model's private reasoning, not part of the answer
            continue
        if part.text:
            texts.append(part.text)
        if part.function_call and tool_request is None:
            provider_data: dict[str, str] = {}
            if part.thought_signature:
                provider_data[_SIGNATURE_KEY] = base64.b64encode(part.thought_signature).decode()
            tool_request = ToolRequest(
                name=part.function_call.name,
                arguments=dict(part.function_call.args or {}),
                id=part.function_call.id,
                provider_data=provider_data,
            )

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else None
    output_tokens = None
    if usage and (usage.candidates_token_count is not None or usage.thoughts_token_count is not None):
        # "thinking" tokens are billed as output too
        output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)

    text = "".join(texts).strip() or None
    if text is None and tool_request is None:
        raise LLMError("Gemini returned neither text nor a tool call (possibly blocked or empty)")
    return LLMResponse(
        text=text, tool_request=tool_request, input_tokens=input_tokens, output_tokens=output_tokens
    )


# ---------- the client --------------------------------------------------------

class GeminiClient(LLMClient):
    """Talks to Google Gemini. Reads GEMINI_API_KEY (and optional GEMINI_MODEL) from the environment."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        _require_sdk()
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.name = f"gemini:{self.model}"
        self._client = genai.Client(api_key=api_key)

    def generate(
        self,
        messages: list[Message],
        tools: list[Tool],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        config_args: dict[str, Any] = {
            "system_instruction": system_prompt,
            # WE run the tools (and record them in the trace), not the SDK.
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if tools:
            config_args["tools"] = [
                types.Tool(function_declarations=[tool_to_declaration(t) for t in tools])
            ]
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=messages_to_contents(messages),
                config=types.GenerateContentConfig(**config_args),
            )
        except genai_errors.APIError as exc:
            raise LLMError(f"Gemini API error {exc.code}: {exc.message}", status_code=exc.code) from exc
        except Exception as exc:  # network problems, timeouts, ...
            raise LLMError(f"could not reach Gemini: {type(exc).__name__}: {exc}") from exc
        return response_to_llm_response(response)

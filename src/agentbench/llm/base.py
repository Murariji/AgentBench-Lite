"""The LLM contract: the "port" every provider (Gemini, Fake, ...) plugs into.

The agent loop (Phase 4) only uses the names in this file, never a vendor SDK.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentbench.tools.base import Tool


class _LLMModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # typos in field names are errors


# What went wrong, in provider-independent words. The runner decides what to do from this.
LLMErrorKind = Literal[
    "auth",              # bad/missing key (401/403)            -> stop immediately
    "rate_limit",        # per-MINUTE limit (requests or tokens) -> wait, then bounded retry
    "quota_exhausted",   # per-DAY limit, or model has no free quota -> stop, don't retry
    "server",            # provider overloaded/broken (5xx)      -> bounded retry
    "network",           # no internet, timeout, connection lost -> bounded retry
    "bad_request",       # our request was invalid (400/404)     -> stop
    "invalid_response",  # reply had no text and no tool call    -> stop
    "unknown",           # anything else                         -> stop
]

# Temporary problems: trying again later can work. Everything else is a hard stop.
RETRYABLE_KINDS: frozenset[str] = frozenset({"rate_limit", "server", "network"})


class LLMError(Exception):
    """Any failure talking to an LLM: missing key, rate limit, network, bad reply.

    Providers convert their own SDK errors into this one type, so the agent loop
    only has to catch ``LLMError`` no matter which provider is used.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: LLMErrorKind = "unknown",
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code  # e.g. 429, 401, 503 (None if not an HTTP error)
        self.retry_after = retry_after  # seconds the provider asked us to wait, if it said

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS


class ToolRequest(_LLMModel):
    """The model ASKING for a tool. It never runs the tool itself; our code does."""

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None  # provider's id for this request, echoed back with the result
    # Opaque provider extras that must be sent back unchanged in the next request
    # (e.g. Gemini's "thought signature"). Other code should not read this.
    provider_data: dict[str, str] = Field(default_factory=dict)


class Message(_LLMModel):
    """One entry in the conversation history sent to the LLM.

    role="user"       text = the question / instruction
    role="assistant"  text and/or tool_request = what the model said or asked for
    role="tool"       tool_request = the request being answered, text = its result
    """

    role: Literal["user", "assistant", "tool"]
    text: str | None = None
    tool_request: ToolRequest | None = None
    is_error: bool = False  # only for role="tool": True if text is an error message

    @model_validator(mode="after")
    def _check_role_fields(self) -> "Message":
        if self.role == "user" and not self.text:
            raise ValueError("a user message needs text")
        if self.role == "assistant" and not self.text and self.tool_request is None:
            raise ValueError("an assistant message needs text or a tool_request")
        if self.role == "tool" and (self.tool_request is None or self.text is None):
            raise ValueError("a tool message needs the tool_request it answers and the result text")
        return self


class LLMResponse(_LLMModel):
    """What the model replied on one turn: final text and/or a tool request, plus tokens."""

    text: str | None = None
    tool_request: ToolRequest | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _text_or_tool(self) -> "LLMResponse":
        if not self.text and self.tool_request is None:
            raise ValueError("an LLMResponse needs text or a tool_request")
        return self

    def to_message(self) -> Message:
        """Turn this reply into an assistant message for the conversation history."""
        return Message(role="assistant", text=self.text, tool_request=self.tool_request)


class LLMClient(ABC):
    """The port. Every provider implements ``generate``; nothing else is required."""

    name: str = "llm"  # shown in traces/dashboard, e.g. "gemini:<model>"

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        tools: list[Tool],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send the WHOLE conversation + the tool menu; return the model's next reply.

        Raise ``LLMError`` on any failure.
        """

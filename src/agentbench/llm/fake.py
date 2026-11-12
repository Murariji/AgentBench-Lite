"""FakeLLM: a pretend model that replies from a script. Free, offline, same result every time."""

from dataclasses import dataclass

from agentbench.llm.base import LLMClient, LLMError, LLMResponse, Message
from agentbench.tools.base import Tool


@dataclass
class FakeCall:
    """What the fake model received on one call, so tests can inspect it."""

    messages: list[Message]
    tool_names: list[str]
    system_prompt: str | None


class FakeLLM(LLMClient):
    """Returns the scripted items in order, one per ``generate`` call.

    An item can be an ``LLMResponse`` (returned) or an ``LLMError`` (raised), so tests
    can simulate 429 / 401 / 503 / network failures without any real API request.
    """

    name = "fake"

    def __init__(self, responses: list[LLMResponse | LLMError]) -> None:
        self._responses = list(responses)  # copy, so the caller's list is not changed
        self.calls: list[FakeCall] = []

    @property
    def remaining(self) -> int:
        """How many scripted items were never used (proves no extra calls were made)."""
        return len(self._responses)

    def generate(
        self,
        messages: list[Message],
        tools: list[Tool],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        self.calls.append(FakeCall(list(messages), [t.name for t in tools], system_prompt))
        if not self._responses:
            raise LLMError("FakeLLM has no scripted responses left")
        item = self._responses.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item

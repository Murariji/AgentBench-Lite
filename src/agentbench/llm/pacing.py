"""Free-tier protection that wraps ANY LLMClient (decorator pattern).

    RateLimitedLLM(inner, pacer, budget)      # behaves exactly like an LLMClient
        generate():
            1. budget.take()   no requests left? -> LLMError("budget_exhausted"), inner NOT called
            2. pacer.wait()    keep at least N seconds between request starts
            3. inner.generate()

The agent loop doesn't know any of this exists: it just sees an LLMClient.
Pacing is conservative spacing, NOT a guarantee against every provider limit.
"""

import time
from collections.abc import Callable

from agentbench.llm.base import LLMClient, LLMError, LLMResponse, Message
from agentbench.tools.base import Tool


class Pacer:
    """Keeps at least ``min_interval_seconds`` between the START of two requests.

    One Pacer is shared by the whole suite, so the gap also holds between tasks.
    """

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative")
        self.min_interval_seconds = min_interval_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_start: float | None = None
        self.total_waited = 0.0  # seconds spent waiting, for reports and tests

    def wait(self) -> None:
        if self._last_start is not None:
            gap = self._clock() - self._last_start
            if gap < self.min_interval_seconds:
                pause = self.min_interval_seconds - gap
                self._sleep(pause)
                self.total_waited += pause
        self._last_start = self._clock()


class RequestBudget:
    """A HARD cap on real requests for a whole suite run: it can never be exceeded."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("a request budget must allow at least 1 request")
        self.limit = limit
        self.used = 0

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def take(self) -> None:
        """Reserve one request, or refuse BEFORE anything is sent."""
        if self.used >= self.limit:
            raise LLMError(f"request budget of {self.limit} used up - request not sent",
                           kind="budget_exhausted")
        self.used += 1


class RateLimitedLLM(LLMClient):
    """An LLMClient that adds a request budget and pacing in front of another LLMClient."""

    def __init__(self, inner: LLMClient, pacer: Pacer, budget: RequestBudget | None = None) -> None:
        self._inner = inner
        self._pacer = pacer
        self._budget = budget
        self.name = inner.name  # traces still show the real model

    def generate(
        self,
        messages: list[Message],
        tools: list[Tool],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        if self._budget is not None:
            self._budget.take()  # checked FIRST: no waiting for a request we won't send
        self._pacer.wait()
        return self._inner.generate(messages, tools, system_prompt)

"""AgentRunner: the agent loop (ReAct = Reason + Act).

    messages = [task prompt]
    repeat up to task.max_steps times:
        reply = llm.generate(messages, tools)        # with bounded retries
        if reply asks for a tool:
            run it, record a Step, add request + result to messages, continue
        else:
            record the final Step, stop -> "completed"
    out of steps -> "max_steps"; unrecoverable LLM error -> "error"

Request budget: at most  task.max_steps x retry.max_attempts  LLM calls per run.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from agentbench.llm.base import NOT_SENT_KINDS, LLMClient, LLMError, LLMResponse, Message
from agentbench.models import RetryEvent, RunResult, RunStatus, Step, Task, ToolCall, Trace, _utc_now
from agentbench.tools.base import Tool
from agentbench.tools.registry import ToolRegistry

DEFAULT_SYSTEM_PROMPT = (
    "You are a careful assistant that solves tasks step by step. "
    "Use the provided tools whenever they help, especially for arithmetic. "
    "When you know the final answer, reply with the answer only."
)


@dataclass(frozen=True)
class RetryPolicy:
    """When and how long to wait before trying an LLM call again."""

    max_attempts: int = 3          # per LLM call, INCLUDING the first try
    base_delay: float = 1.0        # backoff: 1s, 2s, 4s, ... (doubles each retry)
    max_delay: float = 30.0        # our own backoff never waits longer than this
    max_retry_after: float = 60.0  # if the provider asks us to wait longer, stop instead

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if min(self.base_delay, self.max_delay, self.max_retry_after) < 0:
            raise ValueError("delays cannot be negative")

    def delay_for(self, attempt: int, error: LLMError) -> float | None:
        """Seconds to wait before the next attempt, or None meaning "do not retry"."""
        if not error.retryable or attempt >= self.max_attempts:
            return None
        if error.retry_after is not None:  # the provider told us how long: respect it
            return error.retry_after if error.retry_after <= self.max_retry_after else None
        return min(self.base_delay * 2 ** (attempt - 1), self.max_delay)


class AgentRunner:
    """Runs one Task with an LLM and tools, and records everything in a Trace."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        retry: RetryPolicy = RetryPolicy(),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        # Dependency injection: everything the runner needs is handed in from outside,
        # so tests can pass FakeLLM, a fake sleep (no real waiting) and a fake clock.
        self._llm = llm
        self._registry = tools
        self._system_prompt = system_prompt
        self._retry = retry
        self._sleep = sleep
        self._clock = clock

    # ---------- the loop -------------------------------------------------------

    def run(self, task: Task) -> RunResult:
        start = self._clock()
        steps: list[Step] = []
        llm_calls = 0
        retries: list[RetryEvent] = []  # recorded from now on: [] means "none happened"

        def finish(status: RunStatus, *, answer: str | None = None,
                   error: str | None = None, kind: str | None = None) -> RunResult:
            return RunResult(
                task_id=task.id,
                status=status,
                final_answer=answer,
                trace=Trace(task_id=task.id, steps=steps),
                duration_seconds=max(0.0, self._clock() - start),
                error=error,
                error_kind=kind,
                llm_calls=llm_calls,
                retries=retries,
            )

        tools, problem = self._tools_for(task)
        if problem:  # a broken task: stop BEFORE spending any API request
            return finish("error", error=problem, kind="config")

        messages = [Message(role="user", text=task.prompt)]
        for index in range(task.max_steps):
            response, error, attempts, events = self._generate(messages, tools, index)
            llm_calls += attempts
            retries.extend(events)
            if error is not None:
                return finish("error", error=str(error), kind=error.kind)

            if response.tool_request is None:  # final answer -> done
                steps.append(self._step(index, response))
                return finish("completed", answer=response.text)

            # The model asked for a tool: WE run it, then show it the result.
            call = self._run_tool(task, response)
            steps.append(self._step(index, response, call))
            messages.append(response.to_message())
            messages.append(Message(
                role="tool",
                tool_request=response.tool_request,
                text=call.output if call.error is None else call.error,
                is_error=call.error is not None,  # tool errors are FEEDBACK, not a crash
            ))

        return finish("max_steps")

    # ---------- helpers --------------------------------------------------------

    def _tools_for(self, task: Task) -> tuple[list[Tool], str | None]:
        """The tool menu for this task (None = all, [] = none, list = only those)."""
        names = self._registry.names() if task.allowed_tools is None else task.allowed_tools
        unknown = [n for n in names if self._registry.get(n) is None]
        if unknown:
            return [], f"task {task.id!r} allows tools that are not registered: {unknown}"
        return [self._registry.get(n) for n in names], None

    def _generate(
        self, messages: list[Message], tools: list[Tool], step_index: int
    ) -> tuple[LLMResponse | None, LLMError | None, int, list[RetryEvent]]:
        """One LLM call with bounded retries -> (response, error, attempts used, retry events).

        Every failed attempt that is followed by a wait and another try becomes a RetryEvent.
        Once the call is over, all its events get ``succeeded`` = did the call finally work.
        """
        attempt = 0
        failed: list[dict] = []  # retried attempts of THIS call; finished into RetryEvents below

        def done(response, error, used) -> tuple:
            events = [RetryEvent(**f, succeeded=response is not None) for f in failed]
            return response, error, used, events

        while True:  # ends: success, non-retryable error, or attempt limit (see delay_for)
            attempt += 1
            try:
                return done(self._llm.generate(messages, tools, self._system_prompt), None, attempt)
            except LLMError as error:
                if error.kind in NOT_SENT_KINDS:  # refused locally: this attempt never reached the API
                    return done(None, error, attempt - 1)
                delay = self._retry.delay_for(attempt, error)
                if delay is None:
                    if error.retryable:  # temporary problem, but we're out of patience
                        error = LLMError(f"{error} (gave up after {attempt} attempt(s))",
                                         kind=error.kind, status_code=error.status_code,
                                         retry_after=error.retry_after, request_id=error.request_id)
                    return done(None, error, attempt)
                failed.append(dict(step_index=step_index, attempt=attempt, error_kind=error.kind,
                                   status_code=error.status_code, waited_seconds=delay,
                                   request_id=error.request_id, occurred_at=_utc_now()))
                self._sleep(delay)
            except Exception as exc:  # a bug inside an LLM client: report, never crash
                return done(None, LLMError(f"{type(exc).__name__}: {exc}", kind="unknown"), attempt)

    def _run_tool(self, task: Task, response: LLMResponse) -> ToolCall:
        request = response.tool_request
        if task.allowed_tools is not None and request.name not in task.allowed_tools:
            return ToolCall(
                tool_name=request.name,
                arguments=request.arguments,
                error=f"tool {request.name!r} is not allowed for this task; "
                      f"allowed: {task.allowed_tools}",
            )
        return self._registry.execute(request.name, request.arguments)

    @staticmethod
    def _step(index: int, response: LLMResponse, call: ToolCall | None = None) -> Step:
        return Step(
            index=index,
            llm_output=response.text or "",
            tool_call=call,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

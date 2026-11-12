"""Core data models (the "contracts") used by every part of AgentBench-Lite.

Flow of data:
    Task  ──run──►  Trace (list of Step, each may hold a ToolCall)  ──►  RunResult

All models are Pydantic models, so they:
  * validate their data when created (bad data raises ``pydantic.ValidationError``)
  * convert to/from JSON with ``model_dump_json()`` / ``model_validate_json()``
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The only ways a run can end. Using Literal means any other value is rejected.
RunStatus = Literal["success", "failed", "error", "max_steps"]


def _utc_now() -> datetime:
    """Current time in UTC (timezone-aware, so it is unambiguous when stored)."""
    return datetime.now(timezone.utc)


class _BaseModel(BaseModel):
    """Shared settings for all our models.

    extra="forbid": unknown fields raise an error instead of being silently
    ignored, so a typo like ``promt="..."`` is caught immediately.
    """

    model_config = ConfigDict(extra="forbid")


class Task(_BaseModel):
    """What the agent is asked to do."""

    id: str = Field(min_length=1, description="Unique task id, e.g. 'math-001'.")
    prompt: str = Field(min_length=1, description="Instruction given to the agent.")
    expected_answer: str | None = Field(
        default=None, description="Reference answer, used by evaluators later."
    )
    allowed_tools: list[str] = Field(
        default_factory=list, description="Names of tools the agent may use."
    )
    max_steps: int = Field(default=10, gt=0, description="Safety limit for the agent loop.")


class ToolCall(_BaseModel):
    """One use of a tool: what was called, with what, and what came back."""

    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None  # set if the tool succeeded
    error: str | None = None   # set if the tool failed

    @model_validator(mode="after")
    def _not_both_output_and_error(self) -> "ToolCall":
        # A tool call either succeeded or failed — never both.
        if self.output is not None and self.error is not None:
            raise ValueError("a ToolCall cannot have both 'output' and 'error'")
        return self


class Step(_BaseModel):
    """One turn of the agent loop."""

    index: int = Field(ge=0, description="Position in the trace: 0, 1, 2, ...")
    llm_output: str = Field(description="What the model said/decided on this turn.")
    tool_call: ToolCall | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
    # Token usage reported by the LLM for this turn (None if the provider didn't say).
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Trace(_BaseModel):
    """Full, ordered recording of one run. The central data structure."""

    task_id: str = Field(min_length=1)
    steps: list[Step] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def _steps_in_order(cls, steps: list[Step]) -> list[Step]:
        # Step indexes must be exactly 0, 1, 2, ... with no gaps or reordering.
        for expected, step in enumerate(steps):
            if step.index != expected:
                raise ValueError(
                    f"step indexes must be 0..n-1 in order; "
                    f"found {step.index} at position {expected}"
                )
        return steps


class RunResult(_BaseModel):
    """Outcome of running one Task: how it ended, the answer, and the full trace."""

    task_id: str = Field(min_length=1)
    status: RunStatus
    final_answer: str | None = None
    trace: Trace
    duration_seconds: float = Field(ge=0)

"""The Tool contract: what every tool must provide."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class ToolError(Exception):
    """Raised by a tool for an *expected* failure (bad input, not found, ...).

    The registry turns it into ``ToolCall.error`` so the agent can see it and retry.
    """


class Tool(ABC):
    """Base class for all tools.

    Subclasses set the three class attributes and implement ``run``.
    ABC + @abstractmethod: Python refuses to create a Tool that lacks ``run``.
    """

    name: ClassVar[str]          # unique id the LLM uses, e.g. "calculator"
    description: ClassVar[str]   # tells the LLM WHEN to use this tool
    # Behaviour version: a positive whole number, starting at 1. Raise it by 1 whenever what the
    # tool DOES changes (e.g. the calculator starts accepting round()). There is deliberately NO
    # default: ToolRegistry refuses a tool without an explicit version. The contract (name,
    # description, parameters) is fingerprinted automatically - see agentbench.models.ToolSpec.
    version: ClassVar[int]
    # JSON-Schema description of the arguments. LLM providers (Phase 3)
    # use this format to know what arguments to send.
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """Do the work and return the result as text.

        Raise ``ToolError`` for expected failures.
        """

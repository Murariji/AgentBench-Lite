"""ToolRegistry: holds tools by name and executes them safely."""

import copy
from typing import Any

from agentbench.models import ToolCall, ToolSpec
from agentbench.tools.base import Tool, ToolError


class ToolRegistry:
    """A name -> Tool lookup table with a crash-proof ``execute``."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if not getattr(tool, "name", ""):
            raise ValueError(f"{type(tool).__name__} has no 'name'")
        version = getattr(tool, "version", None)
        if type(version) is not int or version < 1:   # type() check: True/False are not versions
            raise ValueError(f"tool {tool.name!r} needs an explicit version: a whole number >= 1 "
                             f"(got {version!r})")
        if tool.name in self._tools:
            raise ValueError(f"a tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        """A snapshot of every registered tool (name, version, description, parameters), by name."""
        return [ToolSpec(name=t.name, version=t.version, description=t.description,
                         parameters=copy.deepcopy(t.parameters))
                for t in (self._tools[n] for n in self.names())]

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolCall:
        """Run a tool and ALWAYS return a ToolCall — never raise.

        Success -> ToolCall.output is set.  Any failure -> ToolCall.error is set.
        """
        arguments = arguments or {}
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolCall(
                tool_name=tool_name,
                arguments=arguments,
                error=f"unknown tool {tool_name!r}; available: {self.names()}",
            )
        try:
            output = tool.run(**arguments)
        except ToolError as exc:          # expected failure reported by the tool
            error = str(exc)
        except TypeError as exc:          # wrong/missing argument names
            error = f"bad arguments: {exc}"
        except Exception as exc:          # bug inside the tool — still don't crash
            error = f"{type(exc).__name__}: {exc}"
        else:
            return ToolCall(tool_name=tool_name, arguments=arguments, output=str(output))
        return ToolCall(tool_name=tool_name, arguments=arguments, error=error)

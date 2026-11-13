"""Tests for tools and the tool registry."""

import pytest

from agentbench.models import ToolCall
from agentbench.tools import (
    CalculatorTool,
    LookupTool,
    Tool,
    ToolError,
    ToolRegistry,
    WordCountTool,
)


@pytest.fixture
def registry() -> ToolRegistry:
    """A registry with all three built-in tools. pytest builds a fresh one per test."""
    return ToolRegistry(
        [CalculatorTool(), WordCountTool(), LookupTool({"Capital of France": "Paris"})]
    )


# ---------- Tool base class --------------------------------------------------

def test_tool_without_run_cannot_be_created():
    class Broken(Tool):
        name = "broken"
        description = "missing run()"

    with pytest.raises(TypeError):
        Broken()


# ---------- calculator -------------------------------------------------------

@pytest.mark.parametrize(
    "expression, expected",
    [("2+2", "4"), ("(2 + 3) * 4", "20"), ("10 / 4", "2.5"), ("8 / 2", "4"), ("-3 ** 2", "-9")],
)
def test_calculator_valid(expression, expected):
    assert CalculatorTool().run(expression=expression) == expected


@pytest.mark.parametrize(
    "expression", ["1/0", "__import__('os')", "abc", "2 +", "9 ** 999", "'a' * 3"]
)
def test_calculator_rejects_bad_or_unsafe_input(expression):
    with pytest.raises(ToolError):
        CalculatorTool().run(expression=expression)


# ---------- word_count / lookup ---------------------------------------------

def test_word_count():
    assert WordCountTool().run(text="  the quick   brown fox ") == "4"


def test_lookup_is_case_insensitive_and_reports_missing():
    tool = LookupTool({"Capital of France": "Paris"})
    assert tool.run(key="  capital OF france ") == "Paris"
    with pytest.raises(ToolError):
        tool.run(key="capital of mars")


# ---------- registry ---------------------------------------------------------

def test_registry_names_and_get(registry):
    assert registry.names() == ["calculator", "lookup", "word_count"]
    assert isinstance(registry.get("calculator"), CalculatorTool)
    assert registry.get("nope") is None


def test_registry_rejects_duplicate_names(registry):
    with pytest.raises(ValueError):
        registry.register(CalculatorTool())


def test_execute_success_returns_toolcall_with_output(registry):
    call = registry.execute("calculator", {"expression": "6*7"})
    assert isinstance(call, ToolCall)
    assert call.output == "42" and call.error is None
    assert call.arguments == {"expression": "6*7"}


@pytest.mark.parametrize(
    "tool_name, arguments, error_contains",
    [
        ("teleport", {}, "unknown tool"),                       # tool doesn't exist
        ("calculator", {"expression": "1/0"}, "division by zero"),  # ToolError
        ("calculator", {"expr": "1+1"}, "bad arguments"),       # wrong argument name
        ("calculator", {}, "bad arguments"),                    # missing argument
        ("lookup", {"key": "unknown"}, "no fact found"),
    ],
)
def test_execute_never_raises_records_error(registry, tool_name, arguments, error_contains):
    call = registry.execute(tool_name, arguments)
    assert call.output is None
    assert error_contains in call.error


def test_execute_catches_unexpected_bugs_in_tools():
    class Buggy(Tool):
        name = "buggy"
        version = 1          # Step A.1: every registered tool declares its version
        description = "always crashes"

        def run(self) -> str:
            raise RuntimeError("oops")

    call = ToolRegistry([Buggy()]).execute("buggy")
    assert call.error == "RuntimeError: oops"

"""Tests for tools and the tool registry."""

import re

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


# ---------- calculator version 2 (Step A.3): round / abs / min / max ------------------

@pytest.mark.parametrize("expression, expected", [
    # half away from zero - NOT Python's round(), which sends ties to the even number
    ("round(0.5)", "1"), ("round(1.5)", "2"), ("round(2.5)", "3"),
    ("round(-0.5)", "-1"), ("round(-2.5)", "-3"),
    # decimal edge cases: the SHORTEST printed form is rounded, not the binary value
    ("round(2.675, 2)", "2.68"), ("round(1.005, 2)", "1.01"), ("round(-2.675, 2)", "-2.68"),
    ("round(0.125, 2)", "0.13"), ("round(16107.32)", "16107"), ("round(23.809523809523807, 1)", "23.8"),
    # computed values: rounded as Python prints them
    ("round(2416098 / 150)", "16107"), ("round(0.1 + 0.2, 2)", "0.3"),
    # negative digits round to tens, hundreds, ...
    ("round(1234, -1)", "1230"), ("round(1235, -1)", "1240"), ("round(-1250, -2)", "-1300"),
    ("round(15, -1)", "20"), ("round(123456789, -10)", "0"),
    # large and small values
    ("round(1e15 + 0.5)", "1000000000000001"), ("round(123456789012.345, 2)", "123456789012.35"),
    # (very small results print in scientific notation, as every float has since v1: a known limitation)
    ("round(1e-300, 10)", "0"), ("round(0.00000000015, 10)", "2e-10"),
    ("round(5)", "5"), ("round(5, 2)", "5"),
])
def test_round_half_away_from_zero(expression, expected):
    assert CalculatorTool().run(expression=expression) == expected


def test_python_round_would_have_been_different():
    # Why the calculator does NOT use Python's built-in round(): documented, not assumed.
    assert round(2.5) == 2 and round(2.675, 2) == 2.67
    assert CalculatorTool().run(expression="round(2.5)") == "3"
    assert CalculatorTool().run(expression="round(2.675, 2)") == "2.68"


@pytest.mark.parametrize("expression, expected", [
    ("abs(-3)", "3"), ("abs(2.5)", "2.5"), ("min(3, 1, 2)", "1"), ("max(3, 1, 2)", "3"), ("min(7)", "7"),
    ("max(21, 26) - min(21, 26)", "5"), ("round(abs(-2.5))", "3"), ("round(max(1.25, 1.2), 1)", "1.3"),
    ("max(" + ", ".join(["1"] * 20) + ")", "1"),           # exactly at the limit
])
def test_allowed_functions(expression, expected):
    assert CalculatorTool().run(expression=expression) == expected


@pytest.mark.parametrize("expression, message", [
    ("sqrt(4)", "function 'sqrt' is not allowed"),
    ("__import__('os')", "function '__import__' is not allowed"),
    ("eval('1')", "function 'eval' is not allowed"),
    ("pow(2, 3)", "function 'pow' is not allowed"),
    ("math.floor(2.5)", "only these functions can be called"),
    ("(lambda: 1)()", "only these functions can be called"),
    ("round(2.5, ndigits=1)", "does not accept keyword arguments"),
    ("max(*[1, 2])", "argument unpacking (*) is not allowed"),
    ("max(" + ", ".join(["1"] * 21) + ")", "max() takes 1 to 20 argument(s) (got 21)"),
    ("min()", "min() takes 1 to 20 argument(s) (got 0)"),
    ("abs(1, 2)", "abs() takes exactly 1 argument(s) (got 2)"),
    ("round(1, 2, 3)", "round() takes 1 to 2 argument(s) (got 3)"),
    ("round(1.5, 11)", "digits must be a whole number from -10 to 10 (got 11)"),
    ("round(1.5, -11)", "digits must be a whole number from -10 to 10 (got -11)"),
    ("round(1.5, 1.0)", "digits must be a whole number from -10 to 10 (got 1.0)"),
    ("round(1e308 * 10)", "cannot round inf"),
    ("round(1 / 0)", "division by zero"),                   # errors inside arguments still caught
    ("max(1, 2 ** 101)", "exponent too large"),
    ("round(x)", "unsupported syntax: Name"),               # variables are still not allowed
    ("round('a')", "unsupported syntax: Constant"),
    ("round(True)", "unsupported syntax: Constant"),
    ("[1, 2]", "unsupported syntax: List"),
])
def test_v2_rejects_everything_else(expression, message):
    with pytest.raises(ToolError, match=re.escape(message)):
        CalculatorTool().run(expression=expression)


def test_too_many_arguments_are_refused_before_any_work():
    # 21 arguments that would each fail: the arity check must come first.
    with pytest.raises(ToolError, match=r"max\(\) takes 1 to 20"):
        CalculatorTool().run(expression="max(" + ", ".join(["1/0"] * 21) + ")")

"""Three simple, deterministic built-in tools."""

import ast
import math
import operator
from decimal import ROUND_HALF_UP, Decimal, localcontext

from agentbench.tools.base import Tool, ToolError

# Allowed math operations. Anything else (names, function calls, imports...) is rejected.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_EXPONENT = 100  # stops "9**9**9" from freezing the program

# ---- version 2: exactly these functions may be called (Step A.3) ---------------
_MAX_FUNCTION_ARGS = 20       # min()/max() take at most this many arguments
_ROUND_DIGITS = range(-10, 11)  # round(x, digits): digits from -10 to 10
_ARITY = {"abs": (1, 1), "round": (1, 2), "min": (1, _MAX_FUNCTION_ARGS), "max": (1, _MAX_FUNCTION_ARGS)}
_ALLOWED = ", ".join(sorted(_ARITY))


def _to_decimal(value: int | float) -> Decimal:
    """int -> exact. float -> through its SHORTEST printed form (repr), never its exact binary value.

    2.675 is stored in binary as 2.67499999999999982236...; Decimal(2.675) would keep that error and
    round DOWN. Decimal(repr(2.675)) == Decimal("2.675"): what the agent typed / Python prints.
    """
    return Decimal(value) if isinstance(value, int) else Decimal(repr(value))


def _round_half_away_from_zero(value: int | float, digits: int = 0) -> int | float:
    """round(2.5) = 3, round(-2.5) = -3, round(2.675, 2) = 2.68, round(1234, -1) = 1230.

    NOT Python's built-in round(), which sends ties to the EVEN number (round(2.5) == 2) and works on
    the binary value (round(2.675, 2) == 2.67). decimal.ROUND_HALF_UP = ties away from zero.
    """
    if isinstance(value, float) and not math.isfinite(value):
        raise ToolError(f"cannot round {value}")
    with localcontext() as ctx:
        ctx.prec = 400   # enough digits for any float (max ~1.8e308): quantize never runs out
        result = _to_decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return int(result) if digits <= 0 else float(result)


class CalculatorTool(Tool):
    """Evaluates arithmetic safely by walking the parsed syntax tree.

    We never call eval(): eval("__import__('os').remove(...)") would run anything.
    Version 2 also allows exactly four functions - round, abs, min, max - called plainly
    (no attributes, keyword arguments or * unpacking), with argument limits.

    Version history:
      v1  + - * / // % ** only; any function call -> "unsupported syntax: Call"
      v2  adds round (half away from zero, via Decimal), abs, min, max   (Step A.3)
    """

    name = "calculator"
    version = 2
    description = ("Evaluate an arithmetic expression, e.g. '(2 + 3) * 4'. Supports + - * / // % ** and the "
                   "functions round(x, digits), abs(x), min(a, b, ...), max(a, b, ...). "
                   "round() rounds halves away from zero (2.5 -> 3).")
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "Arithmetic expression"}},
        "required": ["expression"],
    }

    def run(self, expression: str) -> str:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            raise ToolError(f"invalid expression: {expression!r}") from None
        result = self._eval(tree.body)
        # 4.0 -> "4" so answers look natural
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)

    def _eval(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](self._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = self._eval(node.left), self._eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
                raise ToolError(f"exponent too large (max {_MAX_EXPONENT})")
            try:
                return _BIN_OPS[type(node.op)](left, right)
            except ZeroDivisionError:
                raise ToolError("division by zero") from None
        if isinstance(node, ast.Call):
            return self._call(node)
        raise ToolError(f"unsupported syntax: {type(node).__name__}")

    def _call(self, node: ast.Call) -> int | float:
        # 1. The SHAPE of the call is checked before any argument is calculated.
        if not isinstance(node.func, ast.Name):          # e.g. math.floor(...), (lambda: 1)()
            raise ToolError(f"only these functions can be called: {_ALLOWED}")
        name = node.func.id
        if name not in _ARITY:                            # e.g. sqrt, __import__, eval
            raise ToolError(f"function {name!r} is not allowed; allowed: {_ALLOWED}")
        if node.keywords:
            raise ToolError(f"{name}() does not accept keyword arguments")
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise ToolError("argument unpacking (*) is not allowed")
        low, high = _ARITY[name]
        if not low <= len(node.args) <= high:
            expected = f"exactly {low}" if low == high else f"{low} to {high}"
            raise ToolError(f"{name}() takes {expected} argument(s) (got {len(node.args)})")
        # 2. Only now: calculate the arguments (each one with the same safe rules).
        args = [self._eval(arg) for arg in node.args]
        if name == "round":
            digits = args[1] if len(args) == 2 else 0
            if type(digits) is not int or digits not in _ROUND_DIGITS:
                raise ToolError(f"round() digits must be a whole number from -10 to 10 (got {digits!r})")
            return _round_half_away_from_zero(args[0], digits)
        if name == "abs":
            return abs(args[0])
        return min(args) if name == "min" else max(args)


class WordCountTool(Tool):
    """Counts words in a piece of text."""

    name = "word_count"
    version = 1
    description = "Count the number of words in a text."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Text to count words in"}},
        "required": ["text"],
    }

    def run(self, text: str) -> str:
        return str(len(text.split()))


class LookupTool(Tool):
    """Looks up a fact in a small in-memory table (a stand-in for search/database tools)."""

    name = "lookup"
    version = 1
    description = "Look up a fact by key, e.g. 'capital of france'. Case-insensitive."
    parameters = {
        "type": "object",
        "properties": {"key": {"type": "string", "description": "What to look up"}},
        "required": ["key"],
    }

    def __init__(self, facts: dict[str, str]) -> None:
        # Normalise keys once so lookups are case/space-insensitive.
        self._facts = {k.strip().lower(): v for k, v in facts.items()}

    def run(self, key: str) -> str:
        value = self._facts.get(key.strip().lower())
        if value is None:
            raise ToolError(f"no fact found for {key!r}")
        return value

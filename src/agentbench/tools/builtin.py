"""Three simple, deterministic built-in tools."""

import ast
import operator

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


class CalculatorTool(Tool):
    """Evaluates arithmetic safely by walking the parsed syntax tree.

    We never call eval(): eval("__import__('os').remove(...)") would run anything.
    """

    name = "calculator"
    version = 1
    description = "Evaluate an arithmetic expression, e.g. '(2 + 3) * 4'. Supports + - * / // % **."
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
        raise ToolError(f"unsupported syntax: {type(node).__name__}")


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

PHASE 2 NOTES - TOOLS
AgentBench-Lite | completed 2026-11-11
=====================================================================

Goal: give the agent ACTIONS. No LLM yet - the "hands" before the "brain".

    registry.execute("calculator", {"expression": "6*7"})
        -> ToolCall(tool_name="calculator", arguments={...}, output="42")


=====================================================================
PART 1 - FILES (src/agentbench/tools/)
=====================================================================

base.py       Tool (abstract base class) + ToolError
registry.py   ToolRegistry: register / get / names / execute
builtin.py    CalculatorTool, WordCountTool, LookupTool
__init__.py   re-exports -> `from agentbench.tools import ToolRegistry`


=====================================================================
PART 2 - KEY IDEAS
=====================================================================

ABC + @abstractmethod
    A class that cannot be instantiated until subclasses implement the
    abstract methods. Forgetting run() -> TypeError on creation.

ClassVar
    Marks name/description/parameters as belonging to the CLASS,
    shared by all instances (not per-object data).

name / description / parameters
    What the LLM will see in Phase 3. description = WHEN to use it,
    parameters (JSON Schema) = WHAT arguments to send.

ToolError vs other exceptions
    ToolError = expected failure (division by zero, not found).
    TypeError = wrong/missing argument names.
    Anything else = a bug in the tool.
    execute() catches ALL of them -> ToolCall.error. Never crashes the
    agent loop; the agent can read the error and retry.

try / except / else
    `else` runs only if no exception happened - success path.

Why no eval()
    eval runs ANY Python: eval("__import__('os').remove('file')").
    We parse with ast.parse() and walk the tree, allowing only numbers
    and + - * / // % **. Exponent capped at 100 (9**999 is blocked).

**arguments
    run(**{"expression": "2+2"}) == run(expression="2+2").
    The LLM gives a dict; ** unpacks it into keyword arguments.


=====================================================================
PART 3 - TESTS (tests/test_tools.py)
=====================================================================

@pytest.fixture   builds a fresh registry for every test that asks for it
parametrize       many inputs, one test (valid math, unsafe inputs,
                  every kind of execute() failure)

Result: 37 passed (14 earlier + 23 new).


=====================================================================
PART 4 - SELF-CHECK
=====================================================================

1. Why does execute() return a ToolCall instead of raising?
2. What could go wrong if the calculator used eval()?
3. What is `description` for, if no code in Phase 2 reads it?
4. Why is the exponent capped?
5. What does `else:` in try/except/else do?

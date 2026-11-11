PHASE 1 NOTES - CORE DATA MODELS
AgentBench-Lite | completed 2026-11-11
=====================================================================

Goal: define the data "contracts" every later phase uses. No agent
logic yet - just validated data shapes.

    Task --run--> Trace (Steps, each may hold a ToolCall) --> RunResult


=====================================================================
PART 1 - THE 5 MODELS (src/agentbench/models.py)
=====================================================================

Task       what to do: id, prompt, expected_answer, allowed_tools,
           max_steps (default 10, must be > 0)
ToolCall   one tool use: tool_name, arguments (dict), output OR error
Step       one loop turn: index, llm_output, tool_call?, timestamp (UTC)
Trace      task_id + ordered list of Steps  (THE central structure)
RunResult  task_id, status, final_answer, trace, duration_seconds

status is one of: "success" | "failed" | "error" | "max_steps"

RunResult = WHAT HAPPENED. Whether it was CORRECT is a separate
EvaluationResult, coming in Phase 5. Keep running and judging apart.


=====================================================================
PART 2 - PYDANTIC IDEAS USED
=====================================================================

BaseModel          class whose type hints are ENFORCED at creation.
ValidationError    raised when data doesn't fit the model.
Field(...)         per-field rules:
                     gt=0  greater than 0      ge=0  zero or more
                     min_length=1  no empty strings
                     default=... / default_factory=list
default_factory    builds a NEW list per object (never share one
                   mutable default between objects).
Literal[...]       only these exact values allowed.
X | None = None    optional field, empty by default.
ConfigDict(extra="forbid")
                   unknown fields are errors -> typos like `promt` caught.
@field_validator   custom check on ONE field (Trace: steps 0..n-1).
@model_validator(mode="after")
                   custom check across fields after normal validation
                   (ToolCall: not both output and error).
model_dump_json()  model -> JSON text
model_validate_json(text)   JSON text -> model (validated again)


=====================================================================
PART 3 - TESTS (tests/test_models.py)
=====================================================================

pytest.raises(ValidationError)   assert that bad data is rejected
@pytest.mark.parametrize         same test, several inputs
JSON round trip                  dump -> load -> equal to original;
                                 proves storage (Phase 7) and API
                                 (Phase 9) will work.

Result: 14 passed (12 new + 2 smoke).


=====================================================================
PART 4 - COMMANDS
=====================================================================

python -m pip install -e ".[dev]"   reinstall -> picks up pydantic
pytest                              run all tests


=====================================================================
PART 5 - SELF-CHECK
=====================================================================

1. Why does Python alone not stop Task(max_steps="ten")? What does?
2. Why default_factory=list instead of default=[]?
3. What bug does extra="forbid" prevent?
4. Why is EvaluationResult NOT part of RunResult?
5. What does the JSON round-trip test prove?

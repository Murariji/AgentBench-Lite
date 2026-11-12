"""Run ONE shop benchmark task end to end: execution (trace) + evaluation (verdict).

    python scripts/run_shop_task.py                     # FakeLLM, a good agent on shop-003   (free)
    python scripts/run_shop_task.py --mistake           # FakeLLM, the INNER JOIN mistake     (free)
    python scripts/run_shop_task.py --gemini shop-005   # REAL Gemini on any task (about 4-6 free-tier requests)

The tools and the database are always REAL; only FakeLLM's "decisions" are scripted.
"""

import sys

from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.evaluators import evaluate
from agentbench.llm import FakeLLM, LLMResponse, ToolRequest
from agentbench.runner import AgentRunner
from agentbench.suites import get_task, shop_registry
from agentbench.tools import ReadOnlySQLite


def ask(name, **arguments):
    return LLMResponse(tool_request=ToolRequest(name=name, arguments=arguments))


def fake_agent(mistake: bool) -> FakeLLM:
    """Scripted decisions for shop-003. With mistake=True it uses INNER JOIN (a classic error)."""
    join = "JOIN" if mistake else "LEFT JOIN"
    return FakeLLM([
        ask("list_tables"),
        ask("describe_table", table="orders"),
        ask("sql_query", query=f"SELECT COUNT(*) FROM customers c {join} orders o "
                                f"ON o.customer_id = c.id WHERE o.id IS NULL"),
        LLMResponse(text="0" if mistake else "3"),
    ])


def gemini_agent():
    from dotenv import find_dotenv, load_dotenv

    from agentbench.llm.gemini import GeminiClient

    load_dotenv(find_dotenv(usecwd=True))
    return GeminiClient()


def short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + " ..."


if __name__ == "__main__":
    args = sys.argv[1:]
    use_gemini = "--gemini" in args
    ids = [a for a in args if a.startswith("shop-")]
    task = get_task(ids[0] if ids else "shop-003")
    if not use_gemini and task.id != "shop-003":
        sys.exit("The FakeLLM demo only has a script for shop-003. Use --gemini for other tasks.")

    if not DEFAULT_DB_PATH.exists():
        build_shop_db(DEFAULT_DB_PATH)  # never overwrites: only builds when missing

    llm = gemini_agent() if use_gemini else fake_agent(mistake="--mistake" in args)
    with ReadOnlySQLite(DEFAULT_DB_PATH) as db:
        result = AgentRunner(llm, shop_registry(db)).run(task)          # EXECUTION
    evaluation = evaluate(task, result)                                 # EVALUATION

    print(f"Task     : {task.id} - {task.prompt}")
    print(f"LLM      : {llm.name}\n")
    print("--- EXECUTION (trace) ---")
    for step in result.trace.steps:
        call = step.tool_call
        if call is None:
            print(f"Step {step.index}: final answer: {step.llm_output!r}")
            continue
        outcome = call.output if call.error is None else f"ERROR: {call.error}"
        print(f"Step {step.index}: {call.tool_name}({short(str(call.arguments), 120)})")
        print(f"         -> {short(outcome)}")
    print(f"Status   : {result.status}" + (f" ({result.error_kind}: {result.error})" if result.error else ""))
    print(f"LLM calls: {result.llm_calls}   Time: {result.duration_seconds:.2f}s\n")

    print("--- EVALUATION (verdict) ---")
    for check in evaluation.checks:
        print(f"  {'PASS' if check.passed else 'FAIL'}  {check.name:16} {check.reason}")
    print(f"\nVerdict  : {'PASSED' if evaluation.passed else 'FAILED'}   (expected: {task.expected_answer})")
    print(f"run_id   : {result.run_id}")

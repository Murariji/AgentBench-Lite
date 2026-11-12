"""Run one Task through the agent loop and print its trace step by step.

    python scripts/run_agent.py            # FakeLLM demo: free, offline, no key, no quota
    python scripts/run_agent.py --gemini   # REAL Gemini (free tier): uses about 2-4 requests
"""

import sys

from agentbench.llm import FakeLLM, LLMResponse, ToolRequest
from agentbench.models import RunResult, Task
from agentbench.runner import AgentRunner
from agentbench.tools import CalculatorTool, LookupTool, ToolRegistry, WordCountTool

TASK = Task(
    id="demo-001",
    prompt="What is 15% of 840, plus the number of words in 'the quick brown fox'?",
    expected_answer="130",
    max_steps=6,
)


def fake_llm() -> FakeLLM:
    """A scripted 'model' that solves TASK the way a good agent would."""
    def tool(name, **args):
        return LLMResponse(tool_request=ToolRequest(name=name, arguments=args),
                           input_tokens=220, output_tokens=20)
    return FakeLLM([
        tool("calculator", expression="0.15 * 840"),
        tool("word_count", text="the quick brown fox"),
        tool("calculator", expression="126 + 4"),
        LLMResponse(text="130", input_tokens=300, output_tokens=5),
    ])


def gemini_llm():
    from dotenv import find_dotenv, load_dotenv

    from agentbench.llm.gemini import GeminiClient

    load_dotenv(find_dotenv(usecwd=True))
    return GeminiClient()


def print_result(result: RunResult, llm_name: str) -> None:
    print(f"Task    : {TASK.prompt}")
    print(f"LLM     : {llm_name}\n")
    for step in result.trace.steps:
        tokens = f"[tokens {step.input_tokens}/{step.output_tokens}]"
        if step.tool_call:
            call = step.tool_call
            outcome = call.output if call.error is None else f"ERROR: {call.error}"
            print(f"Step {step.index}: tool {call.tool_name}({call.arguments}) -> {outcome}  {tokens}")
        else:
            print(f"Step {step.index}: final answer: {step.llm_output}  {tokens}")
    print(f"\nStatus  : {result.status}" + (f"  ({result.error_kind}: {result.error})" if result.error else ""))
    print(f"Answer  : {result.final_answer}   (expected: {TASK.expected_answer})")
    print(f"LLM calls: {result.llm_calls}   Time: {result.duration_seconds:.2f}s")


if __name__ == "__main__":
    llm = gemini_llm() if "--gemini" in sys.argv else fake_llm()
    registry = ToolRegistry([CalculatorTool(), WordCountTool(), LookupTool({"capital of france": "Paris"})])
    print_result(AgentRunner(llm, registry).run(TASK), llm.name)

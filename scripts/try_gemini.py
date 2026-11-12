"""Make ONE real round trip with Gemini, using our tools. Uses 2 requests of your free quota.

    python scripts/try_gemini.py                 # ask a question that needs the calculator
    python scripts/try_gemini.py --list-models   # show model names your key can use
    python scripts/try_gemini.py --check-key     # check the key's FORMAT (never prints the key)
"""

import os
import sys

from dotenv import dotenv_values, find_dotenv, load_dotenv

from agentbench.llm import LLMError, Message
from agentbench.llm.gemini import GeminiClient
from agentbench.tools import CalculatorTool, LookupTool, ToolRegistry, WordCountTool

# Remember whether the key was ALREADY set before reading .env (load_dotenv does not override it).
_KEY_SET_BEFORE_DOTENV = "GEMINI_API_KEY" in os.environ
_ENV_FILE = find_dotenv(usecwd=True)
# Copy the settings from .env (searched from the current folder upwards) into the environment.
load_dotenv(_ENV_FILE)


def check_key() -> None:
    """Describe the key without revealing it."""
    print(".env file found     :", _ENV_FILE or "NO - create it with: Copy-Item .env.example .env")
    file_key = dotenv_values(_ENV_FILE).get("GEMINI_API_KEY") if _ENV_FILE else None
    if _KEY_SET_BEFORE_DOTENV:
        print("WARNING             : GEMINI_API_KEY was already set outside .env; THAT value is used.")
    key = os.environ.get("GEMINI_API_KEY", "")
    print("key in .env         :", "yes" if file_key else "NO")
    print("still the template  :", "YES - replace your-key-here and SAVE" if key == "your-key-here" else "no")
    print("length              :", len(key))
    print("first 4 characters  :", key[:4])
    print("contains spaces     :", "YES - remove them" if " " in key else "no")
    print("contains quotes     :", "YES - remove them" if any(q in key for q in "\"'") else "no")


def list_models() -> None:
    client = GeminiClient()
    try:
        names = [m.name for m in client._client.models.list()
                 if "generateContent" in (m.supported_actions or [])]
    except Exception as exc:
        raise LLMError(f"could not list models: {exc}") from exc
    for name in names:
        print(name)


def round_trip() -> None:
    llm = GeminiClient()
    registry = ToolRegistry([CalculatorTool(), WordCountTool(), LookupTool({"capital of france": "Paris"})])
    tools = [registry.get(name) for name in registry.names()]
    system_prompt = "You are a careful assistant. Use the calculator for any arithmetic."

    messages = [Message(role="user", text="What is 15% of 840?")]
    print(f"Model: {llm.name}\n")
    print("USER     :", messages[0].text)

    # Request 1: the model should ASK for the calculator.
    reply = llm.generate(messages, tools, system_prompt)
    print("GEMINI   :", reply.text or "", "| tool request:", reply.tool_request and reply.tool_request.name,
          reply.tool_request and reply.tool_request.arguments)
    print(f"           tokens in/out: {reply.input_tokens}/{reply.output_tokens}")
    if reply.tool_request is None:
        print("\n(The model answered without a tool. That's allowed, but less reliable.)")
        return

    # OUR code runs the tool (the model never does).
    call = registry.execute(reply.tool_request.name, reply.tool_request.arguments)
    print("TOOL     :", call.output if call.error is None else f"ERROR {call.error}")

    # Request 2: send the WHOLE history + the tool result back.
    messages.append(reply.to_message())
    messages.append(Message(
        role="tool",
        tool_request=reply.tool_request,
        text=call.output if call.error is None else call.error,
        is_error=call.error is not None,
    ))
    final = llm.generate(messages, tools, system_prompt)
    print("GEMINI   :", final.text)
    print(f"           tokens in/out: {final.input_tokens}/{final.output_tokens}")


if __name__ == "__main__":
    try:
        if "--check-key" in sys.argv:
            check_key()
        elif "--list-models" in sys.argv:
            list_models()
        else:
            round_trip()
    except LLMError as exc:
        print(f"\nLLM error: {exc}")
        sys.exit(1)

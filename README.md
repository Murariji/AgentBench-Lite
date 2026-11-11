# AgentBench-Lite

**An AI Agent Evaluation & Reliability Framework** — run LLM-powered agents on tasks,
record every step, measure performance and analyze why they fail.

> **Status: early development.** Project skeleton, core data models and tools exist today.
> Sections below are marked ✅ **Implemented** or 🗓️ **Planned**.

## What it will do

An AI agent is a loop: the LLM reads a task, decides to call a tool, sees the result,
and repeats until it gives a final answer. AgentBench-Lite wraps that loop with:

| Component | Purpose | Status |
|---|---|---|
| **Runner** | Execute an agent on a task with tools and a step limit | 🗓️ Planned |
| **Tracer** | Record every step: prompt, tool call, arguments, result, timing, tokens | 🗓️ Planned |
| **Evaluator** | Decide whether the task was completed correctly | 🗓️ Planned |
| **Analyzer** | Categorize failures (wrong tool, bad arguments, loops, wrong answer) | 🗓️ Planned |
| **LLM layer** | Provider-independent interface; Google Gemini first, Ollama/Groq later | 🗓️ Planned |

## Implemented so far

- ✅ Installable Python package (`agentbench`) using the `src/` layout
- ✅ pytest setup with a smoke test verifying the installed package imports
- ✅ Core data models (Pydantic) in `agentbench.models`: `Task`, `ToolCall`, `Step`, `Trace`, `RunResult`
  — validated on creation, JSON round-trip tested
- ✅ Tools (`agentbench.tools`): `Tool` base class, crash-proof `ToolRegistry`, and built-in
  `calculator` (safe, no `eval`), `word_count`, `lookup`

## Tech stack

- Python 3.11+
- Pydantic v2 (data models & validation)
- pytest (testing)
- Planned: asyncio, SQLite, FastAPI, Docker

## Getting started

```powershell
# 1. Create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the package in editable mode, with development tools
python -m pip install -e ".[dev]"

# 3. Run the tests
pytest
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## Project layout

```
AgentBench-Lite/
├── src/agentbench/     # the Python package (application code)
├── tests/              # pytest tests
├── docs/               # architecture notes and decision records
├── pyproject.toml      # metadata, dependencies, tool configuration
└── PROJECT_STATUS.md   # current progress and next steps
```

## Roadmap

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the phase-by-phase plan and progress,
and [docs/architecture.md](docs/architecture.md) for the planned design.

## License

[MIT](LICENSE)

# AgentBench-Lite

**An AI Agent Evaluation & Reliability Platform** — run LLM-powered agents on tasks,
record every step, measure performance, analyze why they fail, and view it all in a dashboard.

> **Status: early development.** Data models, tools, LLM layer (FakeLLM + Gemini) and the agent loop exist today.
> Sections below are marked ✅ **Implemented** or 🗓️ **Planned**.

## What it will do

An AI agent is a loop: the LLM reads a task, decides to call a tool, sees the result,
and repeats until it gives a final answer. AgentBench-Lite wraps that loop with:

| Component | Purpose | Status |
|---|---|---|
| **Runner** | Execute an agent on a task with tools and a step limit | ✅ Implemented |
| **Tracer** | Record every step: prompt, tool call, arguments, result, timing, tokens | ✅ Implemented |
| **Evaluator** | Decide whether the task was completed correctly | 🗓️ Planned |
| **Analyzer** | Categorize failures (wrong tool, bad arguments, loops, wrong answer) | 🗓️ Planned |
| **LLM layer** | Provider-independent interface; Google Gemini first, Ollama/Groq later | ✅ Implemented |
| **Benchmarks** | Run task suites, compute metrics, compare agent configurations | 🗓️ Planned |
| **API** | FastAPI REST backend with SQLite storage | 🗓️ Planned |
| **Dashboard** | React + TypeScript UI for runs, traces and charts | 🗓️ Planned |

## Implemented so far

- ✅ Installable Python package (`agentbench`) using the `src/` layout
- ✅ pytest setup with a smoke test verifying the installed package imports
- ✅ Core data models (Pydantic) in `agentbench.models`: `Task`, `ToolCall`, `Step`, `Trace`, `RunResult`
  — validated on creation, JSON round-trip tested
- ✅ Tools (`agentbench.tools`): `Tool` base class, crash-proof `ToolRegistry`, and built-in
  `calculator` (safe, no `eval`), `word_count`, `lookup`
- ✅ LLM layer (`agentbench.llm`): provider-independent `LLMClient`, `FakeLLM` for offline tests,
  `GeminiClient` (free tier) with tool calling and token counts
- ✅ Agent loop (`agentbench.runner.AgentRunner`): ReAct loop with step limit, tool-error feedback,
  bounded retries (429 per-minute / 5xx / network), hard stop on auth errors and daily quota,
  and a full trace of every step

## Tech stack

- Python 3.11+
- Pydantic v2 (data models & validation)
- pytest (testing)
- Google Gemini API, free tier (`google-genai`), `python-dotenv` — optional extra
- Planned: SQLite, FastAPI, React + TypeScript + Tailwind CSS + Recharts, Docker

## Getting started

```powershell
# 1. Create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the package in editable mode, with development tools
python -m pip install -e ".[dev]"

# 3. Run the tests (no API key needed)
pytest
```

### Optional: real Gemini calls (free tier)

```powershell
python -m pip install -e ".[dev,gemini]"
Copy-Item .env.example .env      # then put your free AI Studio key in .env (never commit it)
python scripts/try_gemini.py     # one real tool-calling round trip
python scripts/run_agent.py --gemini   # full agent loop on a 3-tool task
```

Without any key: `python scripts/run_agent.py` runs the same task with the scripted FakeLLM.

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

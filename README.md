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
| **Evaluator** | Decide whether the task was completed correctly | ✅ Implemented (deterministic) |
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
- ✅ Evaluators (`agentbench.evaluators.evaluate`): separate checks for run status, answer
  (exact / contains / robust number matching with tolerances) and required tool usage;
  verdict = all checks passed, every check explains its reason
- ✅ Data Analyst tools: a fixed-seed sample shop database (SQLite) and read-only `list_tables`,
  `describe_table`, `sql_query`, protected by SQLite itself (read-only mode, `query_only`, an
  allowlist authorizer, size and time limits) — see [SQL tool safety](#sql-tool-safety)

## Evaluation limitations

Evaluators are deterministic: free, instant and repeatable, but they compare text and numbers,
not meaning. "New Delhi" vs "Delhi" is a mismatch, and a contains-check accepts "Not Delhi".
Open-ended answers (summaries, explanations) can't be graded this way; an LLM judge would be
needed, which is out of scope to keep the project at zero cost. Benchmark tasks are therefore
designed to have crisp answers (a number, a name, a category).

## SQL tool safety

The agent's SQL is treated as untrusted input. The security boundary is SQLite itself: the
database path is fixed in code, the file is opened read-only, `PRAGMA query_only` is on, and an
authorizer allowlist permits only reading (SELECT, column reads, functions, recursive CTEs) while
denying writes, schema changes, `ATTACH`, `PRAGMA` and extension loading. Size limits and a
progress-handler time limit stop resource-heavy queries; row and output limits protect token
usage. A text check for SELECT/WITH only exists to give the agent a clear error message.

**Limitations:** this is a constrained read-only SQL tool, not an operating-system sandbox. It
does not protect against bugs in SQLite itself, everything in the database is readable by the
agent (never store secrets there), the time limit is approximate (checked every 1,000 SQLite
steps, not a strict wall-clock timeout), and it cannot stop semantically wrong queries — those
are agent mistakes, which is exactly what the benchmark measures.

```powershell
python scripts/build_shop_db.py   # builds data/shop.db (refuses to overwrite; --rebuild to replace)
```

## Tech stack

- Python 3.11+
- Pydantic v2 (data models & validation)
- pytest (testing)
- SQLite (Python's built-in `sqlite3`) for the benchmark database
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

# Architecture (planned)

> This describes the **intended** design. Implemented so far: the package skeleton and
> **Models** (`src/agentbench/models.py`), **Tools** (`src/agentbench/tools/`) and the
> **LLM layer** (`src/agentbench/llm/`). Update this file whenever the design changes.

## Platform layers

```
┌────────────────────────────────────────────┐
│ Dashboard (React + TypeScript)  — Phase 10  │  displays only, no agent logic
└──────────────────────┬─────────────────────┘
                       │ HTTP + JSON (REST)
┌──────────────────────▼─────────────────────┐
│ API (FastAPI)  — Phase 9                    │  thin layer: request → framework → JSON
└───────────┬──────────────────────┬─────────┘
            │ Python calls         │ save / load
┌───────────▼──────────────┐  ┌────▼─────────────┐
│ Framework (pure Python)  │─►│ SQLite — Phase 7  │
│ models, tools, LLM,      │  │ tasks, runs,      │
│ runner, evaluators, ...  │  │ traces, results   │
└───────────┬──────────────┘  └──────────────────┘
            │ HTTPS
      ┌─────▼─────┐
      │ Gemini API │
      └───────────┘
```

**Rules**
- The framework works on its own (importable Python); API and dashboard are optional layers on top.
- The dashboard talks only to the API — never to the database or the framework directly.
- Pydantic models are the shared data shapes: the API returns them as JSON to the dashboard.
- Long benchmark runs: `POST /runs` returns a `run_id` immediately; the dashboard polls
  `GET /runs/{run_id}` until the run is finished.

## The core loop

```
Task ──► Runner ──► LLMClient.decide() ──► tool call? ──yes──► Tool.run() ──┐
            ▲                                   │                            │
            │                                   no                           │
            │                                   ▼                            │
            │                             final answer                       │
            └──────────────── result appended to Trace ◄─────────────────────┘

Trace ──► Evaluator (did it succeed?) ──► Analyzer (why did it fail?) ──► SQLite / reports
```

## Components

| Component | Responsibility | Depends on |
|---|---|---|
| Models ✅ | Pydantic data types: `Task`, `ToolCall`, `Step`, `Trace`, `RunResult` | — |
| Tools ✅ | `Tool` base class + registry of callable tools | Models |
| LLM layer ✅ | `LLMClient` interface; `FakeLLM` for tests, `GeminiClient` first real provider | Models |
| Runner | The agent loop, step limit, error handling, trace recording | Models, Tools, LLM |
| Evaluators | Score a `RunResult` against the task's expected outcome | Models |
| Analyzer | Classify failures from traces | Models |
| Storage | Persist runs and traces in SQLite | Models |
| Benchmark runner | Run task suites with an `AgentConfig`; metrics; compare configs | Runner, Evaluators |
| API | FastAPI REST service exposing tasks, runs, traces and metrics | Framework, Storage |
| Dashboard | React + TypeScript UI: tasks, runs, trace viewer, charts | API only |

## Design principles

1. **The trace is the central data structure.** Evaluation and analysis only read traces.
2. **Depend on interfaces, not providers.** Only `llm/<provider>.py` files know about a
   specific vendor SDK. See [ADR 0001](decisions/0001-provider-independent-llm.md).
3. **Deterministic tests.** Unit tests use `FakeLLM`; no network or API key required.
4. **Minimal dependencies.** Add a library only when a phase needs it.

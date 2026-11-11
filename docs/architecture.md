# Architecture (planned)

> This describes the **intended** design. Implemented so far: the package skeleton and
> **Models** (`src/agentbench/models.py`) and **Tools** (`src/agentbench/tools/`). Update this file whenever the design changes.

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
| LLM layer | `LLMClient` interface; `FakeLLM` for tests, `GeminiClient` first real provider | Models |
| Runner | The agent loop, step limit, error handling, trace recording | Models, Tools, LLM |
| Evaluators | Score a `RunResult` against the task's expected outcome | Models |
| Analyzer | Classify failures from traces | Models |
| Storage | Persist runs and traces in SQLite | Models |
| API | FastAPI service exposing runs and results | All |

## Design principles

1. **The trace is the central data structure.** Evaluation and analysis only read traces.
2. **Depend on interfaces, not providers.** Only `llm/<provider>.py` files know about a
   specific vendor SDK. See [ADR 0001](decisions/0001-provider-independent-llm.md).
3. **Deterministic tests.** Unit tests use `FakeLLM`; no network or API key required.
4. **Minimal dependencies.** Add a library only when a phase needs it.

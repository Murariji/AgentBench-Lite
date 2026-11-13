# Architecture (planned)

> This describes the **intended** design. Implemented so far: the package skeleton and
> **Models** (`src/agentbench/models.py`), **Tools** (`src/agentbench/tools/`) and the
> **LLM layer** (`src/agentbench/llm/`) the **Runner** (`src/agentbench/runner.py`) and
> **Evaluators** (`src/agentbench/evaluators.py`), the **shop dataset** (`src/agentbench/datasets/`)
> the read-only **SQL tools** (`src/agentbench/tools/sql.py`), the **shop suite**
> (`src/agentbench/suites/`), the **benchmark runner** and **metrics**, and **result storage**
> (`src/agentbench/storage.py`). Update this file whenever the design changes.

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
- Long benchmark runs: `POST /suites` returns a `suite_id` immediately; the dashboard polls
  `GET /suites/{suite_id}` until the run is finished.

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
| Tools ✅ | `Tool` base class + registry; builtin + read-only SQL tools | Models |
| Datasets ✅ | Fixed-seed benchmark data (shop SQLite DB), built on demand | — |
| Suites ✅ | Benchmark tasks (shop: 10 tasks) + the registry of tools they need | Models, Tools |
| LLM layer ✅ | `LLMClient` interface; `FakeLLM` for tests, `GeminiClient` first real provider | Models |
| Runner ✅ | The agent loop, step limit, error handling, trace recording | Models, Tools, LLM |
| Evaluators ✅ | Judge a `RunResult` against the task: separate checks → `EvaluationResult` | Models |
| Analyzer | Classify failures from traces | Models |
| Storage | Persist runs and traces in SQLite | Models |
| Benchmark runner | Run task suites with an `AgentConfig`; metrics; compare configs | Runner, Evaluators |
| API | FastAPI REST service exposing tasks, runs, traces and metrics | Framework, Storage |
| Dashboard | React + TypeScript UI: tasks, runs, trace viewer, charts | API only |

## Execution vs. evaluation

The runner records **what happened** (`RunResult`, status `completed | max_steps | error`).
Evaluators decide **whether it was right** (`EvaluationResult`, list of `Check`s, linked by
`run_id`). Evaluation never calls an LLM, so saved runs can be re-graded for free.

## Design principles

1. **The trace is the central data structure.** Evaluation and analysis only read traces.
2. **Depend on interfaces, not providers.** Only `llm/<provider>.py` files know about a
   specific vendor SDK. See [ADR 0001](decisions/0001-provider-independent-llm.md).
3. **Deterministic tests.** Unit tests use `FakeLLM`; no network or API key required.
4. **Minimal dependencies.** Add a library only when a phase needs it.

## Result storage (Phase 7)

Two separate SQLite files, both git-ignored:

| File | Contents | Who reads it |
|---|---|---|
| `data/shop.db` | customers, products, orders (the benchmark's data) | the agent, read-only, through the SQL tools |
| `data/results.db` | suite runs, task versions, run records, traces, checks, skipped runs | `ResultStore` only |

The agent must never see results or answers, so the two are never the same file.

```
suite_runs ─┬─< suite_tasks >── task_versions     one row per distinct task definition (sha256)
            ├─< run_records ─┬─< steps            trace; tool call = optional columns, args = JSON
            │                ├─< checks           evaluation; none for infrastructure errors
            │                └─< retries          retried LLM requests (schema v2)
            └─< skipped_runs                      runs that never happened, with the reason
```

- **IDs:** `suite_id` = one benchmark execution, `run_id` = one task execution (primary key of
  `run_records`), `task_id` = the benchmark task. A task *version* is identified by `task_hash`.
- **History stays interpretable:** each suite links to the exact task definitions it used, stored once
  per distinct content. Editing a prompt or tolerance creates a new version; old runs keep theirs.
- **Integrity:** foreign keys on every connection, primary/unique keys, CHECK rules, every value a `?`
  parameter, and a whole suite saved in one transaction (all or nothing).
- **Schema version:** `PRAGMA user_version` (currently 2). Older files are upgraded by `MIGRATIONS`
  (one step per version, all in one transaction, rolled back on failure). Newer versions, or tables
  without a version, are refused rather than misread. Runs stored before v2 have
  `retries_recorded = 0`: their retries are unknown, not zero.
- **Queries:** `list_suites()` (newest first, counts by SQL `GROUP BY`) and `task_history(task_id)`
  (every run of a task, including skipped ones, with its task version) are what the API will serve.
- **Persistence is not execution:** a failed save raises `StorageError` and never changes the benchmark
  result, which stays in memory and can still be exported to JSON.

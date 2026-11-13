# AgentBench-Lite

**An AI Agent Evaluation & Reliability Platform** — run LLM-powered agents on tasks,
record every step, measure performance, analyze why they fail, and view it all in a dashboard.

> **Status: active development.** The Python framework (agent loop, Gemini + FakeLLM, SQL tools,
> evaluators, benchmark runner, metrics, comparison) and SQLite result storage exist today;
> failure analysis, the API and the dashboard are next.
> Sections below are marked ✅ **Implemented** or 🗓️ **Planned**.

## What it will do

An AI agent is a loop: the LLM reads a task, decides to call a tool, sees the result,
and repeats until it gives a final answer. AgentBench-Lite wraps that loop with:

| Component | Purpose | Status |
|---|---|---|
| **Runner** | Execute an agent on a task with tools and a step limit | ✅ Implemented |
| **Tracer** | Record every step: prompt, tool call, arguments, result, timing, tokens | ✅ Implemented |
| **Evaluator** | Decide whether the task was completed correctly | ✅ Implemented (deterministic) |
| **Analyzer** | Categorize failures (guessing, tool misuse, loops, unfixed errors, misread or wrong results) with evidence, plus near-miss warnings | ✅ Implemented |
| **LLM layer** | Provider-independent interface; Google Gemini first, Ollama/Groq later | ✅ Implemented |
| **Benchmarks** | Run task suites, compute metrics, compare agent configurations, free-tier safety | ✅ Implemented |
| **Storage** | SQLite history of every run, trace and check; queries and a results CLI | ✅ Implemented |
| **API** | FastAPI REST backend over the framework and storage | ✅ Implemented (local) |
| **Dashboard** | React + TypeScript UI for runs, traces and charts | 🔶 In progress (runs, details, traces, failures, task history, compare, pass-rate chart, start a run) |

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
- ✅ Shop Data Analyst benchmark (`agentbench.suites`): 10 tasks (COUNT → LEFT JOIN traps →
  multi-table revenue → percentages); every expected answer proven by independent reference SQL
- ✅ Suite runner + metrics (`agentbench.benchmark`, `agentbench.metrics`): run a suite with repeats,
  pass rate over eligible runs, by difficulty, steps / LLM calls / tokens / time, tool errors,
  most-failed checks, pass@k and pass^k
- ✅ Reports + comparison (`agentbench.report`): text report, side-by-side comparison that checks
  fairness (same tasks, grading and dataset; which config dimension changed), and lossless JSON
  export to `results/` so saved runs can be re-graded for free

## Try the benchmark (free, no API key)

```powershell
python scripts/run_benchmark.py --compare            # careful vs sloppy scripted agents: 10/10 vs 6/10
python scripts/run_benchmark.py --agent sloppy --save   # also writes results/<suite>_<config>_<time>.json
```

The careful and sloppy agents are **scripted** (fixed answers written in advance, not AI). They exist
to test the benchmark pipeline at zero cost, and every report labels them as such.

### Real run (Gemini free tier)

```powershell
python scripts/run_benchmark.py --agent gemini          # prints the request estimate, sends nothing
python scripts/run_benchmark.py --agent gemini --yes    # runs it: >= 6 s pacing, hard cap of 80 requests
```

Safety: an estimate before any request, `--yes` required, a **hard request budget** that can never be
exceeded, and a **circuit breaker** that stops the suite on auth or quota errors (remaining runs are
marked skipped; the suite is reported as incomplete, never as failed by the agent).

**First result** (`gemini-3.5-flash-lite`, 1 repeat): **10/10 passed** (easy 2/2, medium 4/4, hard 4/4),
57 requests, avg 5.7 steps and ~2.6k input tokens per task, 351 s in total. Two tool errors (the model
tried `round(...)` and `datetime(...)` in the calculator) were recovered by the model itself.
**Reliability run** (3 repeats): **30/30, pass@3 10/10, pass^3 10/10**, 170 requests. The model gave
identical answers in every repeat. Findings: two tasks needed a retried request, and shop-010 used all
8 allowed steps in 2 of 3 runs because the model kept trying `round()` in the calculator. A perfect
score also means this suite is too easy to separate configurations for this model, so harder tasks
are a planned next step.

```powershell
python scripts/run_shop_task.py             # scripted agent solves shop-003  -> PASSED
python scripts/run_shop_task.py --mistake   # same task with an INNER JOIN bug -> completed, but FAILED
python scripts/run_shop_task.py --gemini shop-004   # real Gemini (free tier, ~5 requests)
```

Each run prints the execution trace (every SQL query and its result) and the evaluation (every
check with its reason). The `--mistake` run shows why execution and evaluation are separate: the
agent finished and used the right tool, but its answer was wrong.

## Stored results (SQLite)

Every finished benchmark is saved automatically in `data/results.db` (git-ignored). Browse it:

```powershell
python scripts/results.py list                      # all runs, newest first (--real: only real LLMs)
python scripts/results.py show 0af951e0             # full report (short ids work, like git)
python scripts/results.py compare 743cde41 0af951e0 # side by side, with the fairness check
python scripts/results.py history shop-010          # one task across every run
python scripts/results.py import results/*.json     # store exported JSON (duplicates are refused)
```

- **Why SQLite:** built into Python (no server, no dependency, ₹0), one file, real SQL.
- **Why a separate file:** `shop.db` is what the agent may read; `results.db` holds answers, traces and
  scores. The agent's SQL tool can never reach it.
- **Schema:** `suite_runs` → `run_records` → `steps` / `checks`, plus `skipped_runs`, and
  `task_versions` (each distinct task definition stored once, by content hash), so old results keep
  the exact prompt, answer and tolerance they were graded with. See
  [docs/architecture.md](docs/architecture.md#result-storage-phase-7).
- **Transactions:** a whole suite is saved in one transaction, so a crash never leaves half a run.
- **Parameterized SQL:** every value is sent as a `?` parameter, never pasted into SQL text.
- **Tool versions:** every run stores the exact tools it offered (name, declared version,
  description, parameters). Comparisons say "tools changed: calculator v1 -> v2", and runs stored
  before this existed are "tools unknown", never assumed identical.
- **Schema version:** stored in `PRAGMA user_version` (now 3). Older databases are upgraded
  automatically in one transaction (nothing changes if the upgrade fails); unknown versions are refused.
- **Retries:** every retried LLM request is recorded (kind, status, wait, whether it finally
  worked). Runs from before this existed show retries as *not recorded*, never as zero.
- **If saving fails:** the benchmark result is still valid. A warning explains why, and a JSON
  recovery copy is written to `results/` for a later `import`. Nothing is reported as saved unless it was.

## Failure analysis

Why did a run fail? Deterministic rules read the stored trace (no LLM, no API calls, ₹0) and give each
failed run **one primary category, with evidence** (step numbers, tool names, error text), in this
priority order: `invalid_response`, `no_data_used` (answered without ever calling a required tool),
`tool_misuse`, `loop`, `unrecovered_tool_error`, `step_limit`, `misread_result` (the right value was in
the final tool output), `wrong_result` (the answer repeats a wrong tool result), `unparseable_answer`,
and `unclassified` when the evidence is not enough. Infrastructure errors are never agent failures.

Passed runs can still get **near-miss warnings**: near the step limit, recovered or ignored tool errors,
and retried LLM requests (for runs stored before retries were recorded: "not recorded", never zero).

```powershell
python scripts/results.py failures 0af951e0          # every failed run and warning of one stored run
python scripts/results.py failures --all             # categories across all stored runs
```

**Limits:** the rules see what happened, not what the model "thought"; categories are likely patterns.
So far the real Gemini runs had no failures (the suite is too easy for that model), so the categories
are verified on scripted test fixtures; harder tasks are planned.

## The harder suite: shop-hard

The 10 shop tasks turned out too easy for the model we test (40 of 40 real runs passed), so they can't
tell configurations apart. `shop-hard` adds 9 realistic business questions on the same database where a
plausible query gives a wrong answer: a median without a MEDIAN function, "January but not February",
a percentage of ALL customers (LEFT JOIN), units per order vs per line, a revenue share, the largest
monthly decrease, SQLite's weekday numbering, a tie rule, and distinct customers.

- **Hard, not ambiguous:** every rule (precision, ties, definitions) is in the question; each number task
  has its own tolerance.
- **Proven:** every answer is recomputed independently in plain Python; 25 trap answers are rejected.
- **Pre-registered** before any real run: `src/agentbench/suites/registrations/shop-hard.v1.json` freezes
  tasks, answers, grading and tools (with the git commit). A change means a new registered version.
- **Guarded:** before any request, the run is checked against the registration (tasks, answers,
  tolerances, tools, max steps, dataset, and 43 known answers through today's evaluator). A real run
  that differs is refused. Reports say `matches`, `SUBSET … NOT a full-suite result`, or `DIFFERS`.

```powershell
python scripts/run_benchmark.py --suite shop-hard --compare                       # scripted, free
python scripts/run_benchmark.py --suite shop-hard --agent gemini --budget 100     # real: estimate only
```

## The calculator (version 2)

The agent's calculator never uses `eval()`: it walks the parsed expression and allows only arithmetic
(`+ - * / // % **`) and exactly four functions, `round(x, digits)`, `abs(x)`, `min(...)`, `max(...)`,
called plainly (no attributes, keyword arguments or `*` unpacking; min/max take at most 20 arguments,
round digits must be −10…10). `round()` rounds **half away from zero** (2.5 → 3, −2.5 → −3,
2.675 → 2.68) with `Decimal`; a float is converted through its shortest printed form, so binary
artefacts don't change the result. This is deliberately NOT Python's built-in `round()`, which
gives `round(2.5) == 2` and `round(2.675, 2) == 2.67`.

Why version 2: real Gemini runs kept trying `round()` on shop-010, wasting a step on the error and
using 7–8 of 8 allowed steps. Measure the change (stored runs only, no API calls):

```powershell
python scripts/results.py history shop-010     # TOOLS column: fingerprint, or "unknown" for old runs
python scripts/results.py measure shop-010     # exploratory before/after, grouped by agent and tools
```

**Result** (shop-010, 3 new runs vs 4 old ones): the model still calls `round(16107.32)`, which now
works, so the error and the recovery step disappear in every run: 0 tool errors (was 3), 7.00 steps
on average (was 7.75), all answers correct. It did **not** remove the step-limit risk: the runs still
use 7 of 8 steps, mostly exploring the schema (4 of 7 steps). Tiny samples: exploratory evidence.

`measure` reports small samples as **exploratory evidence, not proof**, never mixes a scripted agent
with a real model, and keeps infrastructure errors out of correctness. Known limitation: very small
results print in scientific notation (`2e-10`), as they have since version 1.

## Benchmark metrics

| Metric | Meaning |
|---|---|
| Pass rate | `passed / eligible` — always shown with its denominator, e.g. `5/7 (71.4%)` |
| Eligible run | A run that produced an agent result (finished, hit the step limit, or gave an unusable reply) |
| Infrastructure error | Quota, auth, network, server or configuration failure — **not** the agent's fault, not counted as a failure; the suite is marked **incomplete** |
| Averages | Steps, LLM calls, tokens, duration over eligible runs |
| Totals | LLM calls and duration over all executed runs (that's what quota and time cost) |
| pass@k | With k repeats: share of tasks where **at least one** repeat passed — "can the agent solve it?" |
| pass^k | Share of tasks where **all** k repeats passed — "can I rely on it?" |

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

## Web API (read-only, local)

```powershell
python -m pip install -e ".[dev,api]"
python scripts/serve_api.py                      # http://127.0.0.1:8000/docs  (interactive docs)
```

`GET /suites`, `/suites/{id}`, `/suites/{id}/runs/{run_id}`, `/suites/{id}/failures`,
`/tasks/{task_id}/history`, `/tasks/{task_id}/measure`, `/compare?ids=a&ids=b`, `/registrations`,
`/health`. Paginated lists, short ids, one error format (`{"error": {"code", "message", "details"}}`).
Local only (127.0.0.1), no login. The framework itself does not need FastAPI.

**Runs through the API** (one at a time, in the background):

```powershell
curl -X POST http://127.0.0.1:8000/runs -H "Content-Type: application/json" -d "{\"agent\": \"careful\", \"suite\": \"shop-hard\"}"
curl http://127.0.0.1:8000/runs/<job_id>        # status, completed_tasks / total_tasks, current_task, saved
```

`POST /estimates` shows the cost and whether a run would be allowed, and never sends anything. Scripted
runs are always allowed. **Real Gemini runs are off** unless the server is started with
`--allow-real-runs`, and even then each run needs `confirm: true`, a `budget` within `--max-real-budget`,
and a passing registration guard. Job status lives in memory (lost on restart); results are saved to
SQLite, or to a JSON recovery file if saving fails (`saved: false`, `recovery_path`).

Full reference: **[docs/api.md](docs/api.md)** — endpoints, error codes, job states, the real-run gates,
CORS (only the React dev origins `http://localhost:5173` / `http://127.0.0.1:5173`, never `*`), the 64 KB
request limit, and the pinned API contract that the dashboard relies on.

## Dashboard (in progress)

```powershell
python scripts/serve_api.py          # terminal 1: the API
cd dashboard; npm install; npm run dev   # terminal 2: open http://localhost:5173
```

React + TypeScript + Tailwind, with types generated from the API's pinned contract. It only displays and
requests; all logic stays in the backend. See [dashboard/README.md](dashboard/README.md).

## Tech stack

- Python 3.11+
- Pydantic v2 (data models & validation)
- pytest (testing)
- SQLite (Python's built-in `sqlite3`) for the benchmark database
- Google Gemini API, free tier (`google-genai`), `python-dotenv` — optional extra
- SQLite (built-in `sqlite3`) for stored results, `data/results.db`
- FastAPI + Uvicorn (optional `api` extra) for the local read-only API; httpx for its tests
- React 18 + TypeScript 5 + Vite 5 + Tailwind CSS 3 (dashboard), Vitest + Testing Library
- Planned: Recharts (charts), React Router (pages), Docker

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

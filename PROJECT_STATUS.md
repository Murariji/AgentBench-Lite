# AgentBench-Lite — Project Status

_Last updated: 2026-11-12_

## Goal
An **AI Agent Evaluation & Reliability Platform** with three layers:
1. **Python framework** — run tool-using LLM agents on tasks, trace every step, evaluate
   results, compute metrics (success rate, latency, tokens, tool usage, failures), compare
   agent configurations, and analyze failure patterns. Works on its own, without the API or UI.
2. **FastAPI backend + SQLite** — exposes the framework through REST APIs and stores results.
3. **React + TypeScript dashboard** — create tasks, start benchmarks, view traces and charts.
   Talks only to the API; contains no agent or evaluation logic.

Backend first; the dashboard comes after the API is stable. Each technology is added only
when its phase begins.

## Current state
**Phase 5 — Step 5.2 SQL tools + shop database: ✅ complete.** Tests: **191 passed** (user-reported; 58 new).
- `src/agentbench/datasets/shop.py`: fixed-seed (2026) shop DB — 30 customers / 7 cities, 15 products /
  4 categories, 150 orders Jan–Jun 2026, 369 order items. Edge cases: multi-product orders, 3 customers
  without orders, 2 products never ordered. `build_shop_db(path, overwrite=False)`: refuses to overwrite;
  builds in a temp file then atomic `os.replace`. `scripts/build_shop_db.py [--rebuild]` → `data/shop.db`
  (git-ignored). Verified by user: built, counts as designed.
- `src/agentbench/tools/sql.py`: `ReadOnlySQLite` + `list_tables`, `describe_table`, `sql_query`.
  Engine layers (security boundary): fixed path, `mode=ro`, `PRAGMA query_only`, authorizer ALLOWLIST
  (SELECT, READ, FUNCTION, RECURSIVE; `load_extension` denied), extension loading off, size limits
  (1 MB values, 5,000-char SQL, 0 attached DBs), progress-handler time limit (~2 s, APPROXIMATE),
  one statement only. Our-code layers (messages/tokens only): SELECT/WITH check, 50 rows, 200-char
  cells, 4,000-char output. `describe_table`/`list_tables` never run model SQL.
- Tests: valid analytical SQL allowed (JOIN, GROUP BY, aggregates, WITH, WITH RECURSIVE); attacks blocked
  even with the text check bypassed (`WITH x AS (SELECT 1) DELETE ...`); DB file SHA-256 unchanged after
  every blocked write; timeouts, size and output limits tested. Real `data/shop.db` checked: DELETE
  blocked, file unchanged.
- Fix: tests could not create temp folders in the Windows temp directory ("Access is denied", most likely
  caused by Claude's sandboxed test run). pytest now uses `--basetemp=.pytest_tmp` (git-ignored).
- Limitation (documented): constrained read-only SQL tool, not an OS sandbox; SQLite bugs, readable data,
  approximate time limit and semantically wrong queries are out of its scope.

**Phase 5 — Step 5.1 Evaluators: ✅ complete.** Tests: **133 passed** (user-reported; 44 new).
- `src/agentbench/evaluators.py`: `evaluate(task, result) -> EvaluationResult`. Separate mandatory
  checks: `status`, `answer:<exact|contains|number>`, `required_tools` (only if the task lists any).
  Verdict = all checks passed — no score, no averaging (enforced by a model validator).
- Number check: currency removed from a fixed list (₹ $ € £ Rs INR USD rupees dollars); commas only
  as Western/Indian thousands separators ("1,5" refused); `Decimal` for exact values; multiple
  numbers → only one / after the last marker (=, is, answer:, total:) / all equal, else
  "ambiguous" failure. Configurable `abs_tolerance` / `rel_tolerance` (default 0 = exact).
- Required tools need ≥ 1 SUCCESSFUL call (failed attempts are reported, not counted).
- Models: `Task` + `answer_type`, `abs_tolerance`, `rel_tolerance`, `required_tools`;
  `RunResult.run_id` (uuid4); new `Check(name, passed, reason)`, `EvaluationResult(run_id, ...)`.
- Decided: no `forbidden_tools` (use `allowed_tools`); no score in Step 5.1.
- Known limitation (tested on purpose): text checks don't understand meaning, e.g.
  contains "Delhi" passes for "Not Delhi, it's Mumbai". LLM-as-judge out of scope (₹0 budget).
- Notes: `docs/learning/phase-5-notes.md`.

**Phase 4 — Agent runner: ✅ complete.** Tests: **89 passed** (user-reported).
- `src/agentbench/runner.py`: `AgentRunner.run(task) -> RunResult` (ReAct loop) + `RetryPolicy`.
  Endings: `completed` (final text), `max_steps`, `error`. Tool errors are fed back to the model
  (`is_error=True`) so it can self-correct. Every step recorded (tool call, tokens, timestamp).
- Quota/billing policy (₹0): `LLMError.kind` = auth | rate_limit | quota_exhausted | server |
  network | bad_request | invalid_response | unknown. Retryable only: rate_limit, server, network,
  with bounded exponential backoff (default 3 attempts, 1s→2s, cap 30s). `Retry-After` /
  `RetryInfo` respected; waits > 60s → stop. 429 per-day or zero free quota → hard stop.
  401/403 → immediate stop. Gemini SDK's own retries disabled (`attempts=1`), 60s timeout.
  Request budget per run ≤ `max_steps × max_attempts`; `RunResult.llm_calls` counts every request.
- Model changes: `RunStatus` = completed | max_steps | error (correctness is Phase 5);
  `Task.allowed_tools`: None = all, [] = none, list = only those; `RunResult.error`,
  `error_kind`, `llm_calls`. Task listing unregistered tools → `error_kind="config"`, 0 API calls.
- `FakeLLM` scripts may contain `LLMError`s (simulate 429/401/503/network); `.remaining` property.
- Demo: `scripts/run_agent.py` (FakeLLM, free/offline) → answer 130 in 4 steps.
  Real run `--gemini` (gemini-3.5-flash-lite, user ran it): same 4-step plan, answer 130,
  4 LLM calls, 7.12s, input tokens grew 253→289→322→355 as history was resent.
- 429 classifier tests use hand-written error JSON in Google's documented format; verify
  against the first real 429 seen.
- Notes: `docs/learning/phase-4-notes.md`.

**Phase 3 — LLM layer: ✅ complete.** Tests: **49 passed** (pytest output shared by user).
Real Gemini round trip verified with `gemini-3.5-flash-lite`: model requested
`calculator {'expression': '0.15 * 840'}` → tool returned `126` → model answered "15% of 840 is 126."
(tokens in/out: 217/22, then 253/14).
- `src/agentbench/llm/`: `base.py` (`LLMClient`, `Message`, `ToolRequest`, `LLMResponse`, `LLMError`),
  `fake.py` (`FakeLLM`), `gemini.py` (`GeminiClient` + translation functions). `Step` gained
  `input_tokens` / `output_tokens`.
- Optional extra `gemini` = `google-genai>=3.2`, `python-dotenv>=1`. Key in git-ignored `.env`;
  template `.env.example`. Script: `scripts/try_gemini.py` (`--check-key`, `--list-models`).
- Tests: `tests/test_llm.py` (5), `tests/test_gemini.py` (7, skipped if SDK missing; no network).
- Issues met: (1) first AI Studio key returned 401 `ACCESS_TOKEN_TYPE_UNSUPPORTED` (known issue with
  new `AQ.` keys) → fixed by creating a new key; (2) `gemini-3.8-flash` returned 503 (overloaded) →
  switched default to `gemini-3.5-flash-lite` (larger free quota).
- Notes: `docs/learning/phase-3-notes.md`.

**Phase 2 — Tools: ✅ complete** (user-reported: 37 passed).
- `src/agentbench/tools/`: `base.py` (`Tool` ABC, `ToolError`), `registry.py` (`ToolRegistry`),
  `builtin.py` (`calculator`, `word_count`, `lookup`). Tests: `tests/test_tools.py` (23).
- `ToolRegistry.execute()` never raises: returns `ToolCall` with `output` or `error`.
- Notes: `docs/learning/phase-2-notes.md`. No new dependencies.

**Phase 1 — Core data models: ✅ complete** (user-reported: 14 passed).
- `pyproject.toml`: first runtime dependency `pydantic>=2`.
- `src/agentbench/models.py`: `Task`, `ToolCall`, `Step`, `Trace`, `RunResult` (+ `RunStatus` Literal).
  Rules: `extra="forbid"`; `max_steps > 0`; ToolCall can't have both output and error;
  Trace step indexes must be 0..n-1; UTC timestamps; `duration_seconds >= 0`.
- `tests/test_models.py`: 12 tests (validation + JSON round trip). Notes: `docs/learning/phase-1-notes.md`.
- Names kept from architecture doc; `EvaluationResult` deferred to Phase 5.

**Phase 0 — Project skeleton: ✅ complete** (commit `beba908`, pushed to `origin/main`).
- Files: `pyproject.toml`, `.gitignore`, `README.md`, `LICENSE` (MIT), `docs/architecture.md`,
  `docs/decisions/0001-provider-independent-llm.md`, `src/agentbench/__init__.py`, `tests/test_smoke.py`.
- Environment: Python 3.12.8 in `.venv`; `agentbench-lite 0.1.0` installed editable; pytest 9.2.0.
- Tests: **2 passed** (`tests/test_smoke.py`).
- Fixed: setuptools license deprecation warning → SPDX `license = "MIT"` + `license-files`
  (requires setuptools>=77). Verified: reinstall clean, 2 passed, `License-Expression: MIT`.
- Git: `main` tracks `origin/main` on GitHub. Study notes: `docs/learning/phase-0-notes.md`.
- Docker not installed (not needed until Phase 11).

## Key decisions
| Decision | Choice | Why |
|---|---|---|
| Layout | `src/agentbench/`, dist name `agentbench-lite` | Tests run against the installed package |
| Agent loop | Write our own (no LangChain) | Learning goal: understand the loop |
| LLM access | `LLMClient` interface + providers (ADR 0001) | Provider-independent |
| Real LLM | Google Gemini free tier first; Ollama/Groq later | Free; user preference |
| Tests | `FakeLLM` (scripted replies) | Free, deterministic, offline |
| Models | Pydantic v2, `extra="forbid"` | Validation + JSON for free; typos caught |
| Tool failures | Captured in `ToolCall.error`, never raised | Agent can retry; data for Phase 8 |
| Calculator | AST walk, no `eval()` | Security; exponent capped at 100 |
| Platform layers | Framework → FastAPI → React dashboard | Framework usable alone; UI only displays |
| Long benchmark runs | API returns a `run_id` at once; dashboard polls | UI never freezes |
| Budget | ₹0: free tiers + open source only, billing disabled | Learning/portfolio project |
| LLM errors | One `LLMError` type (with `status_code`) for all providers | Runner catches one thing; 4xx vs 5xx retry policy |
| Thought signatures | Kept opaque in `ToolRequest.provider_data` | Gemini needs them echoed back; rest of code stays provider-free |
| Retries | Runner owns them; SDK retries off; bounded backoff | Never an uncontrolled request loop on a free quota |
| Dependency injection | Runner receives llm, tools, sleep, clock | FakeLLM + instant retry tests |
| Verdict | All checks mandatory; `passed = all(checks)`; no score | Averages hide why a run failed |
| Number grading | Decimal + 4-rule extraction; refuse when unsure | Never silently accept a wrong number |
| SQL safety | SQLite engine layers are the boundary; text check only for messages | Regex can be tricked; an allowlist authorizer can't |
| Dataset | Generated from a fixed seed, built on demand, never committed | Same answers everywhere; no binary files in git |
| Run vs. eval | `RunResult` ≠ `EvaluationResult` | What happened vs. was it correct (Phase 5) |

## Working agreements
- Every file is explained as it is written; commands and git are run manually.
- Minimal implementation; no unnecessary dependencies.
- **Zero budget:** free tiers and open-source tools only; never enable paid billing.
- README separates ✅ Implemented from 🗓️ Planned.
- Verify with tests before a milestone is done; update this file after each milestone.

## Roadmap
- [x] **Phase 0** — Project skeleton, venv, pytest, first commit & push
- [x] **Phase 1** — Core data models (Pydantic): `Task`, `ToolCall`, `Step`, `Trace`, `RunResult`
- [x] **Phase 2** — Tools: `Tool` base + registry; 2–3 simple tools
- [x] **Phase 3** — LLM layer: `LLMClient`, `FakeLLM`, `GeminiClient`
- [x] **Phase 4** — Agent runner: ReAct-style loop, step limit, error handling, tracing
- [ ] **Phase 5** — Evaluators: exact-match, contains, tool-usage; later LLM-as-judge
- [ ] **Phase 6** — Benchmark runner: task suites, batch runs, metrics, agent configs + comparison;
  more realistic tools (SQL query over sample SQLite DB, date calculator, unit converter, file reader)
- [ ] **Phase 7** — Storage: SQLite for runs & traces (adds `run_id`)
- [ ] **Phase 8** — Failure analysis: categorize failures
- [ ] **Phase 9** — FastAPI backend: REST API over the framework and database
- [ ] **Phase 10** — Dashboard: React + TypeScript + Tailwind + Recharts
- [ ] **Phase 11** — Docker: package backend (and dashboard) for one-command start

Planned model additions (added only in their phase): token counts on `Step` (Phase 3),
`AgentConfig` (Phase 6), `run_id` (Phase 7).

## Next step
Phase 5, Step 5.3 — shop task suite (~10 tasks, easy → hard) with every expected answer proven by an
independently written reference SQL query; avoid ambiguous questions (e.g. the 4-way tie for most
customers per city); demo running one task + evaluation. Waiting for user approval.

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
- [ ] **Phase 4** — Agent runner: ReAct-style loop, step limit, error handling, tracing
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
Phase 4 — Agent runner: the loop (LLM → tool → result → repeat), step limit, retries on 429/503
(not on 401), full trace recording. Built and tested with `FakeLLM`. Waiting for user approval.

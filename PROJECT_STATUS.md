# AgentBench-Lite — Project Status

_Last updated: 2026-11-11_

## Goal
A modular Python framework to **run** LLM agents on tasks with tools, **trace** every step,
**evaluate** task completion, and **analyze** failures.

## Current state
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
- Docker not installed (not needed until Phase 9).

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
| Run vs. eval | `RunResult` ≠ `EvaluationResult` | What happened vs. was it correct (Phase 5) |

## Working agreements
- Every file is explained as it is written; commands and git are run manually.
- Minimal implementation; no unnecessary dependencies.
- README separates ✅ Implemented from 🗓️ Planned.
- Verify with tests before a milestone is done; update this file after each milestone.

## Roadmap
- [x] **Phase 0** — Project skeleton, venv, pytest, first commit & push
- [x] **Phase 1** — Core data models (Pydantic): `Task`, `ToolCall`, `Step`, `Trace`, `RunResult`
- [x] **Phase 2** — Tools: `Tool` base + registry; 2–3 simple tools
- [ ] **Phase 3** — LLM layer: `LLMClient`, `FakeLLM`, `GeminiClient`
- [ ] **Phase 4** — Agent runner: ReAct-style loop, step limit, error handling, tracing
- [ ] **Phase 5** — Evaluators: exact-match, contains, tool-usage; later LLM-as-judge
- [ ] **Phase 6** — Benchmark runner: task suites, batch runs, metrics
- [ ] **Phase 7** — Storage: SQLite for runs & traces
- [ ] **Phase 8** — Failure analysis: categorize failures
- [ ] **Phase 9** — FastAPI service + Docker

## Next step
Phase 3 — LLM layer: `LLMClient` interface, `FakeLLM`, `GeminiClient`. Waiting for user approval to start.

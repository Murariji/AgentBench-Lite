# AgentBench-Lite — Project Status

_Last updated: 2026-11-10_

## Goal
A modular Python framework to **run** LLM agents on tasks with tools, **trace** every step,
**evaluate** task completion, and **analyze** failures.

## Current state
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

## Working agreements
- Claude writes files and explains them; user runs commands and manages git.
- Minimal implementation; no unnecessary dependencies.
- README separates ✅ Implemented from 🗓️ Planned.
- Verify with tests before a milestone is done; update this file after each milestone.

## Roadmap
- [x] **Phase 0** — Project skeleton, venv, pytest, first commit & push
- [ ] **Phase 1** — Core data models (Pydantic): `Task`, `ToolCall`, `Step`, `Trace`, `RunResult`
- [ ] **Phase 2** — Tools: `Tool` base + registry; 2–3 simple tools
- [ ] **Phase 3** — LLM layer: `LLMClient`, `FakeLLM`, `GeminiClient`
- [ ] **Phase 4** — Agent runner: ReAct-style loop, step limit, error handling, tracing
- [ ] **Phase 5** — Evaluators: exact-match, contains, tool-usage; later LLM-as-judge
- [ ] **Phase 6** — Benchmark runner: task suites, batch runs, metrics
- [ ] **Phase 7** — Storage: SQLite for runs & traces
- [ ] **Phase 8** — Failure analysis: categorize failures
- [ ] **Phase 9** — FastAPI service + Docker

## Next step
Phase 1 — core data models (Pydantic). Waiting for user approval to start.

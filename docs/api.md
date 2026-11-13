# AgentBench-Lite API reference

A **local** HTTP API (FastAPI) over the AgentBench-Lite framework: stored benchmark runs, traces, failure
analysis, comparisons, and background runs. It adds no agent or evaluation logic of its own.

```powershell
python -m pip install -e ".[dev,api]"
python scripts/serve_api.py                 # http://127.0.0.1:8000  -  interactive docs: /docs
```

- **Local only:** the server always binds `127.0.0.1`; there is no login.
- **Pinned contract:** endpoints, fields and types are pinned in `src/agentbench/api/contract.json`
  (see "Contract" below). The dashboard may rely on them.
- **Scripted agents** (`careful`, `sloppy`) are fixed test fixtures, not AI. Only `gemini` is a real model.

## Endpoints

| Method + path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /` | name, version, links | 200 | 500 |
| `GET /health` | status, schema version, real runs enabled? | 200 | 503 |
| `GET /registrations` | pre-registered suites (shop-hard v1) | 200 | |
| `GET /suites?real_only&limit&offset` | stored runs, newest first, paginated; each with `tasks_fingerprint`, `registration_status`, `scope` (full / subset / unknown) | 200 | 422, 503 |
| `GET /suites/{suite_id}` | one run: config, fingerprints, metrics, registration, run summaries | 200 | 404, 409, 422, 503 |
| `GET /suites/{suite_id}/runs/{run_id}` | one task run: full trace, checks, failure analysis | 200 | 404, 409, 422, 503 |
| `GET /suites/{suite_id}/failures` | failure categories, evidence, near misses | 200 | 404, 409, 422, 503 |
| `GET /tasks/{task_id}/history?limit&offset` | one task across all stored runs | 200 | 404, 422, 503 |
| `GET /tasks/{task_id}/measure` | exploratory before/after, grouped by agent and tools | 200 | 404, 422, 503 |
| `GET /compare?ids=a&ids=b` | 2–5 runs of the SAME suite side by side, with fairness conclusions | 200 | 404, 409, 422, 503 |
| `POST /estimates` | cost + would it be allowed? **never sends anything** | 200 | 413, 422 |
| `POST /runs` | start ONE run in the background | 202 + `Location` | 403, 409, 413, 422 |
| `GET /runs?limit&offset` | jobs started since this server started | 200 | 422 |
| `GET /runs/{job_id}` | job status and progress (poll this) | 200 | 404, 422 |

Every endpoint may also return 500 (unexpected error: only its type is reported, never a traceback or a
secret). Short ids (≥ 4 characters, like a git commit) work for suites, runs and jobs.

## Errors — one shape for everything

```json
{"error": {"code": "not_found", "message": "no suite id starts with 'zzzz9999'", "details": {"suite_id": "zzzz9999"}}}
```

| Status | `code` values | When |
|---|---|---|
| 403 | `real_runs_disabled` | a real run, but the server was not started with `--allow-real-runs` |
| 404 | `not_found` | unknown suite / run / task / job, or an unknown route |
| 405 | `method_not_allowed` | e.g. `DELETE /suites/...` (only GET and POST exist) |
| 409 | `ambiguous_id`, `incompatible_comparison`, `not_analysable`, `registration_mismatch`, `run_in_progress` | conflicts with the current state |
| 413 | `payload_too_large` | request body above 64 KB (counted as it arrives, also for chunked uploads) |
| 422 | `validation_error`, `confirmation_required`, `budget_required`, `budget_too_high` | invalid input |
| 500 | `internal_error` | unexpected error |
| 503 | `storage_unavailable` | the results database cannot be used |

## Is a run a full-suite result? (`scope`)

Each item of `GET /suites` says which task set ran and whether it was the whole suite:
`tasks_fingerprint` (null = task definitions were not stored), `registration_status` (matches, subset,
differs, unregistered, unknown) and `scope`: `full`, `subset` (only some of the suite's tasks — its pass
rate is not a full-suite score), or `unknown` (not enough stored information — never assumed to be full).

## Pagination

```json
"pagination": {"limit": 20, "offset": 40, "total": 57, "returned": 17, "next_offset": null}
```
`limit` 1–100 (default 20), `offset` ≥ 0. `next_offset: null` = last page.

## Runs: estimate, start, poll

```text
POST /estimates  {"agent": "careful", "suite": "shop-hard"}
  -> 200 {"kind": "scripted", "runs": 9, "estimate": null, "allowed": true, "reasons": []}

POST /runs       {"agent": "careful", "suite": "shop-hard"}
  -> 202 {"job_id": "fdae938d...", "status": "running", "completed_tasks": 0, "total_tasks": 9, ...}
     Location: /runs/fdae938d...

GET /runs/fdae938d
  -> 200 {"status": "finished", "completed_tasks": 9, "total_tasks": 9, "percent": 100.0, "current_task": null,
          "saved": true, "recovery_path": null, "summary": {"pass_rate": "9/9 (100.0%)", ...}, "progress": [...]}
```

**Request fields** (`RunIn`; unknown fields are rejected): `agent` (`careful` | `sloppy` | `gemini`),
`suite` (default `shop`), `tasks` (optional subset), `repeats` (1–10), `budget` (≥ 1; required for real
runs), `confirm` (must be `true` for real runs).

**Job states:** `queued` → `running` → `finished` (every scheduled run executed and evaluated) |
`incomplete` (stopped by the budget or the quota, or infrastructure errors — finished runs are kept and
saved) | `failed` (an unexpected program error). **One run at a time:** a second `POST /runs` while one is
active returns `409 run_in_progress`.

**Progress for a progress bar:** `completed_tasks`, `total_tasks`, `percent`, `current_task`,
`current_repeat`, plus human-readable `progress` lines.

**Temporary vs permanent:** job status lives in memory and is lost when the server stops. Results are saved
to SQLite (then visible in `/suites`). If saving fails: `saved: false`, `save_error`, and the exact
`recovery_path` of a JSON copy that can be imported later (`python scripts/results.py import <path>`).
A server stopped in the middle of a run loses that unfinished run.

## Real Gemini runs — four gates, checked on the server

1. the server was started with `--allow-real-runs` — otherwise **403**, and no client is ever built
2. `"confirm": true` — otherwise **422** `confirmation_required`
3. `"budget"` given and ≤ the server's `--max-real-budget` (default 100) — otherwise **422**
4. the registration guard passes (tasks, answers, tolerances, tools, dataset, grading probes) — otherwise
   **409** `registration_mismatch`

Then the run has exactly the command line's protections: ≥ 6 s between requests, the hard budget counting
every request including retries, the circuit breaker on quota/auth errors, infrastructure errors kept apart.
`POST /estimates` with the same body shows the cost and every reason a run would be refused.

**About /docs ("Try it out") and examples:** the examples only pre-fill the form. Nothing is sent until you
click Execute, and the server applies every gate to Swagger like to any other client — the "REAL Gemini"
example is refused with 403 unless the server was started with `--allow-real-runs`.

## Browsers (CORS)

Only `http://localhost:5173` and `http://127.0.0.1:5173` (the React dev server) may read responses in a
browser, plus exact origins added with `--cors-origin`. Never `*`. Methods GET and POST, no credentials;
preflight (`OPTIONS`) requests from those origins are answered, other origins get no permission.
**CORS is a browser rule, not the safety layer:** the real-run gates protect every client.

Other headers: `Cache-Control: no-store` on `/runs` and `/estimates` (a progress bar never sees a cached
status).

## Contract

`src/agentbench/api/contract.json` pins every endpoint (method, path, parameters, request and response
types) and every schema (fields, types, required fields). `tests/test_api_contract.py` fails when the API
differs from it. Changing the contract is deliberate:

```powershell
python scripts/update_api_contract.py                                        # show differences, change nothing
python scripts/update_api_contract.py --write --reason "why it changes"       # record it below
```

## Contract changes

### 2026-11-13 — Initial API contract (Phase 9.3), before the dashboard depends on it

- added endpoint GET /
- added endpoint GET /compare
- added endpoint GET /health
- added endpoint GET /registrations
- added endpoint GET /runs
- added endpoint GET /runs/{job_id}
- added endpoint GET /suites
- added endpoint GET /suites/{suite_id}
- added endpoint GET /suites/{suite_id}/failures
- added endpoint GET /suites/{suite_id}/runs/{run_id}
- added endpoint GET /tasks/{task_id}/history
- added endpoint GET /tasks/{task_id}/measure
- added endpoint POST /estimates
- added endpoint POST /runs
- added schema AgentConfig
- added schema Check
- added schema CompareOut
- added schema ErrorBody
- added schema ErrorResponse
- added schema EstimateOut
- added schema EvaluationResult
- added schema FailuresOut
- added schema HealthOut
- added schema HistoryPage
- added schema IndexOut
- added schema JobOut
- added schema JobPage
- added schema MeasureGroupOut
- added schema MeasureOut
- added schema Pagination
- added schema Rate
- added schema RateOut
- added schema RegisteredSuiteOut
- added schema RegistrationOut
- added schema RetryEvent
- added schema RunAnalysis
- added schema RunDetailOut
- added schema RunIn
- added schema RunRecord
- added schema RunResult
- added schema RunSummaryOut
- added schema Signal
- added schema SkippedRun
- added schema Step
- added schema SuiteAnalysis
- added schema SuiteDetailOut
- added schema SuiteMetrics
- added schema SuitePage
- added schema SuiteSummaryOut
- added schema TaskHistoryEntry
- added schema TaskOutcomesOut
- added schema ToolCall
- added schema ToolSpec
- added schema Trace

### 2026-11-13 — GET /suites items gain tasks_fingerprint, registration_status and scope, so the dashboard can tell subset runs from full-suite runs (e.g. the 2-task shop-hard pilot, the shop-010 measurement); unknown task sets are reported as unknown, never as full

- added field SuiteSummaryOut.registration_status (enum(matches,subset,differs,unregistered,unknown))
- added field SuiteSummaryOut.scope (enum(full,subset,unknown))
- added field SuiteSummaryOut.tasks_fingerprint (null|string)
- CHANGED required fields of SuiteSummaryOut: ['complete', 'config_name', 'failed', 'finished_at', 'infra_errors', 'kind', 'model', 'pass_rate', 'passed', 'provider', 'repeats', 'scheduled_runs', 'short_id', 'skipped', 'started_at', 'stop_reason', 'suite_id', 'suite_name', 'total_llm_calls'] -> ['complete', 'config_name', 'failed', 'finished_at', 'infra_errors', 'kind', 'model', 'pass_rate', 'passed', 'provider', 'registration_status', 'repeats', 'scheduled_runs', 'scope', 'short_id', 'skipped', 'started_at', 'stop_reason', 'suite_id', 'suite_name', 'tasks_fingerprint', 'total_llm_calls']

### 2026-11-13 — GET /suites items gain config_fingerprint (the stored config, same formula as run details) and tools_fingerprint (null when tools were not recorded), so the pass-rate chart never joins runs of different configurations or tools into one line

- added field SuiteSummaryOut.config_fingerprint (string)
- added field SuiteSummaryOut.tools_fingerprint (null|string)
- CHANGED required fields of SuiteSummaryOut: ['complete', 'config_name', 'failed', 'finished_at', 'infra_errors', 'kind', 'model', 'pass_rate', 'passed', 'provider', 'registration_status', 'repeats', 'scheduled_runs', 'scope', 'short_id', 'skipped', 'started_at', 'stop_reason', 'suite_id', 'suite_name', 'tasks_fingerprint', 'total_llm_calls'] -> ['complete', 'config_fingerprint', 'config_name', 'failed', 'finished_at', 'infra_errors', 'kind', 'model', 'pass_rate', 'passed', 'provider', 'registration_status', 'repeats', 'scheduled_runs', 'scope', 'short_id', 'skipped', 'started_at', 'stop_reason', 'suite_id', 'suite_name', 'tasks_fingerprint', 'tools_fingerprint', 'total_llm_calls']

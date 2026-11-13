# Phase 9 notes — a web API (FastAPI)

## The concepts, in plain words

**HTTP.** How programs talk over a network. A client sends a REQUEST = a method + a path
(`GET /suites`); the server sends a RESPONSE = a status code + a body (for us: JSON).

**REST.** URLs name THINGS (resources): `/suites` = the run list, `/suites/42daa8df` = one run,
`/tasks/shop-010/history` = one task's history. The METHOD says what to do: `GET` reads (never
changes anything), `POST` creates or starts something (Step 9.2).

**Endpoint.** One method + path the server answers, written as one small Python function.

**Status codes** — the outcome, readable before the body:
| Code | Meaning | Example in this API |
|---|---|---|
| 200 | OK | the run list |
| 202 | accepted, working on it | starting a run (9.2) |
| 404 | does not exist | unknown suite id, unknown task |
| 405 | method not allowed | `POST /suites` in the read-only API |
| 409 | conflicts with the current state | ambiguous short id; comparing a shop run with a shop-hard run; a suite without task definitions cannot be analysed |
| 422 | your input is invalid | `limit=500`; one id for a comparison; an id with `$` in it |
| 503 | storage unavailable | the results file is not a usable database |

**One error shape.** Every error, whatever happened: `{"error": {"code", "message", "details"}}`, so the
dashboard needs ONE piece of code to show errors.

**Dependency injection.** An endpoint declares `store: ResultStore = Depends(get_store)`; FastAPI opens a
fresh ResultStore for that request and closes it afterwards. SQLite connections are never shared between
threads, and tests point the app at a temporary database — no server, no network.

**Pagination.** Lists come in pages: `?limit=20&offset=40` → items 41–60, plus
`{"limit", "offset", "total", "returned", "next_offset"}` (`next_offset = null` on the last page).

**Background jobs (Step 9.2).** A long run can't make the browser wait: the server answers 202 with a job id
and works in the background; the client POLLS for progress. Job status lives in memory (lost on restart);
results live in SQLite (never lost on restart).

## Step 9.1 — the read-only endpoints

| Endpoint | Returns | Framework function |
|---|---|---|
| `GET /health` | ok, schema version, real runs enabled (false) | — |
| `GET /registrations` | registered suites (shop-hard v1) | `registrations_for` |
| `GET /suites?real_only&limit&offset` | run list, newest first, paginated | `list_suites` |
| `GET /suites/{id}` | one run: config, fingerprints, metrics, registration, run summaries | `load`, `compute_metrics`, `check_suite` |
| `GET /suites/{id}/runs/{run_id}` | one task run: full trace, checks, failure analysis | `load`, `analyze_run` |
| `GET /suites/{id}/failures` | categories, evidence, near misses | `analyze_suite` |
| `GET /tasks/{task_id}/history?limit&offset` | one task across runs | `task_history` |
| `GET /tasks/{task_id}/measure` | exploratory before/after + limitations | `measure_task` |
| `GET /compare?ids=a&ids=b` | side by side, fairness, conclusions | `comparison_conclusions` |

Short ids work (≥ 4 characters). Comparisons need 2–5 distinct runs of the SAME suite.

**Two small framework changes (no behaviour change):** `report.comparison_conclusions()` returns the
comparison's conclusions as data (the text report uses it too), and `storage.AmbiguousSuiteIdError` (a
subclass of SuiteNotFoundError) lets the API answer 409 instead of 404. The storage schema is unchanged.

**Local only.** `scripts/serve_api.py` always binds `127.0.0.1` (there is no `--host` option on purpose).

## Self-check (9.1)
1. Why does `GET /suites/ab` answer 422 but `GET /suites/zzzz9999` answer 404?
2. Why is comparing a shop run with a shop-hard run a 409 and not a 200 with `fair: false`?
3. Why does every request get its own ResultStore?
4. What does `next_offset: null` tell the dashboard?

## Step 9.2 — background runs, locks, and the real-run gates

**Background thread.** `POST /runs` answers at once (202 + job id); a second worker inside the program runs
the benchmark. Like a restaurant: the waiter takes the order and comes back; the cook works in the kitchen.

**Race condition.** Two requests 1 ms apart could both see "no run active" and both start one.
**Lock.** `with self._lock:` — the check AND the creation of the job happen as ONE step; the second
request waits, then sees the first job and gets 409. Proven: moving the check outside the lock (with a tiny
pause) made all 8 simultaneous requests start a run; the test caught it.

**Job states.** queued → running → finished | incomplete (budget, quota, infra errors — finished runs KEPT
and saved) | failed (an unexpected program error). A run stopped by the budget is honest partial work, not
a failure.

**Structured progress** for a progress bar: `completed_tasks / total_tasks`, `percent`, `current_task`,
`current_repeat`, plus the human-readable lines.

**The four gates (agent = gemini)**, checked on the SERVER, so no dashboard button can skip them:
1. server started with `--allow-real-runs` — else 403 `real_runs_disabled` (the client is never built)
2. `confirm: true` — else 422
3. `budget` given and ≤ the server's maximum — else 422
4. registration guard passes — else 409 `registration_mismatch`

**Temporary vs permanent.** Job status is in memory (gone on restart); results are in SQLite (or a JSON
recovery file, reported with its exact path, `saved: false`). Never "saved" unless SQLite committed.

**One rulebook.** `agentbench/runs.py` holds the planning, guard, estimate, Gemini setup and execution
for BOTH the CLI and the API.

**Secrets.** Every message is passed through `redact()`; unexpected errors return only their type.

## Self-check (9.2)
5. Why is checking "is a run active?" outside the lock dangerous, even if it's only one line earlier?
6. The budget runs out during task 2 of 2. Which status does the job get, and is task 1 kept?
7. Why is the real Gemini client built INSIDE the job and not when the request arrives?
8. The server restarts. What happens to `GET /runs/<old id>` and to `GET /suites/<its suite id>`?

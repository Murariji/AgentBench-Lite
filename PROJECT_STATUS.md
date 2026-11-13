# AgentBench-Lite — Project Status

_Last updated: 2026-11-13_

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
**Benchmark v2 — Step A.3 Calculator v2: ✅ complete** (tests: **484 passed**; 73 new), measured.

**A.3 measurement (user ran it, 2026-11-13, suite 42daa8df, gemini-3.5-flash-lite, shop-010 × 3,
budget 30): 21 requests (generic estimate 15; realistic 7/run), 3/3 correct, 0 retries.**
| | before (4 runs, tools unknown) | after (3 runs, calculator v2) |
|---|---|---|
| round() errors | 3/4 runs | 0/3 |
| tool errors | 3 | 0 |
| avg steps | 7.75 | 7.00 |
| avg LLM calls | 8.25 (incl. 2 unrecorded retries) | 7.00 |
| near step limit | 4/4 | 3/3 |
Traces: the model still calls `round(16107.32)`; in v2 it succeeds, so the recovery step
(`calculator(16107.32)`) disappears — the saved step is exactly the wasted one. The LLM-call drop
overstates the effect (old retries were unrelated server errors); steps are the fairer measure.
Not fixed: still 7 of 8 steps, because 4 steps are schema exploration (list_tables + 3 × describe_table).
Exploratory evidence (tiny samples, unknown baseline, behaviour + description changed together).
Idea for later (not planned): a cheaper way to see the schema, measured the same way.

- Calculator **version 2**: exactly `round`, `abs`, `min`, `max`, called plainly (no attributes, keyword
  arguments or `*` unpacking; anything else → "function 'x' is not allowed; allowed: abs, max, min,
  round"). Call shape and argument counts checked BEFORE any argument is calculated. Limits: min/max
  1–20 arguments, round digits −10…10 (whole numbers only), exponent limit, division by zero kept.
- Rounding: half away from zero via `Decimal` + `ROUND_HALF_UP` (2.5 → 3, −2.5 → −3, 2.675 → 2.68,
  1.005 → 1.01, 1234 at −1 → 1230). Conversion rule: int exactly; float through its SHORTEST printed
  form (`repr`), never its exact binary value. Plain arithmetic unchanged from v1 (still floats).
- Description now mentions the functions and the rounding rule → contract fingerprint changed too
  (calculator b6ed49cab787 → fbd30a600ed5; shop tools 2191990ea327 → c1af5a87019e). SQL tool pins unchanged.
- Tripwires did their job: 1 contract pin + 7 v1 behaviour pins failed; replaced by 11 v2 pins (v1 kept
  as history in comments and notes). 7 tests that assumed "calculator = v1" made version-relative;
  one analysis test used `round(30.2)` as a failing call → now `sqrt(900)`.
- `run_benchmark.py --tasks ID [ID ...]` (validated: unknown or duplicate ids refused; suite order kept).
  `results.py history` gains a TOOLS column (fingerprint or "unknown") + a legend per fingerprint.
  New `results.py measure TASK` (`agentbench/measurement.py`): groups by (provider, model, tools) —
  correctness, avg LLM calls/steps, round() errors, tool errors, near step limit, step-limit failures;
  infra errors and skips counted apart; always prints its limitations.
- Found and fixed during the trial: `measure` first grouped by tools only, which put a SCRIPTED agent's
  column next to real Gemini runs (a fake "improvement"). Now grouped by agent too; a mutation check
  (grouping by tools only) makes 2 tests fail.
- Known limitation (unchanged since v1): very small results print in scientific notation (`2e-10`).
- Measurement estimate: the tool's generic estimate says ~15 (5/run); shop-010 history suggests 7–9
  per run (~21–27). The hard cap of 30 is never exceeded; a cut repeat is reported as stopped by budget.

**Benchmark v2 — Step A.1 Tool versions in the fingerprint: ✅ complete** (tests: **411 passed** when run
by Claude; 36 new — user to confirm). Next: A.3 (calculator fix + measurement), waiting for approval.
Order agreed with the user: A.1 → A.3 → A.2 → A.4 (few real runs, gradually) → Phase 9 → Phase 10.
- Versioning convention: `Tool.version` = whole number >= 1, NO default; `ToolRegistry.register()`
  refuses a missing/invalid version. All 6 tools are version 1 (unchanged since Phase 2/5).
- `ToolSpec(name, version, description, parameters)`, `contract_fingerprint` = sha256 of canonical JSON
  (`canonical_json`: sorted keys, no spaces) of name + description + parameters; `tools_fingerprint()`
  over all specs incl. versions, in name order. `ToolRegistry.specs()`.
- `SuiteResult.tools` (None = not recorded) + `tools_fingerprint`; `run_suite` records the registry's specs.
- Comparison: tools = configuration dimension; same → nothing, changed → "Changed dimension: tools" +
  `tool_changes()` ("calculator v1 -> v2", added/removed, "contract changed … with the SAME version"),
  unknown → warning, never "run-to-run variation only". Report: `Tools :` line or "not recorded".
- Storage schema **v3** (`MIGRATIONS[2]`): `suite_runs.tools_recorded` (DEFAULT 0 = unknown),
  `tool_versions` (by hash), `suite_tools`. Genuine v2 fixture (`tests/fixtures/results_v2.sql`, written by
  the Phase 8 code, incl. a recorded retry) + the v1 fixture: both upgrade with every suite identical and
  `tools = None`; failed migration rolls back to v2; fresh = upgraded schema.
- Tripwires: pinned contract fingerprints (calculator b6ed49cab787, describe_table 95015d83cc59,
  list_tables d438d6e99a62, sql_query caad37852689; shop tools 2191990ea327) and 7 calculator-v1
  behaviours (cover known cases only).
- Two Step 8.1 tests had hard-coded "version 2 is newest"; made version-independent.
- Trial on a COPY of the user's results.db: v2 → v3, both Gemini runs intact with tools "not recorded".
- Notes: `docs/learning/benchmark-v2-notes.md`.

**Phase 8 — Failure analysis: ✅ complete** (Steps 8.1, 8.2, 8.3). Tests: **375 passed** when run by
Claude (9 new in 8.3 — user to confirm).

**Step 8.3 Reports and CLI: ✅ complete.**
- `report.format_failures(suite, detailed=False)`: a section at the end of every text report — failed
  runs of evaluated, each category with its count (priority order) and one example with evidence,
  infrastructure errors apart with their kinds, skipped runs, near-miss counts, and "retries not recorded
  for N run(s) … unknown, not zero". `detailed=True`: every failed run with all additional signals, and
  every warning per run. Results without task definitions: "not available".
- `RunAnalysis.infra_error_kind` (e.g. quota_exhausted) for the infra line.
- `python scripts/results.py failures <id>` (detailed) and `failures --all [--real]` (per suite + totals
  across all stored runs). Both re-analyse STORED traces: no LLM, no API calls.
- On a copy of the user's real data: Gemini 0/40 failed; near misses: near_step_limit ×9,
  unrecorded_retries_likely ×5, recovered_tool_errors ×3, unfixed_tool_errors ×1 (shop-002's ignored
  `datetime(...)` calculator error in the first run).
- Honest limitation: real runs have produced no failures yet (ceiling effect), so the analyser is only
  proven on scripted fixtures. A "benchmark v2" (harder tasks, a tools version in the fairness
  fingerprint) would give it real failures; it needs a real run (~60 requests).


**Step 8.2 Failure classifier: ✅ complete.**
- `src/agentbench/analysis.py`: `analyze_run(task, record) -> RunAnalysis` (category, signals with
  evidence/step indexes/tool names, warnings, `retries_recorded`), `analyze_suite(suite) -> SuiteAnalysis`
  (category and warning counts, examples, failed/passed/infra/skipped, retries not recorded).
- One detector per category, `PRIORITY` = invalid_response, no_data_used, tool_misuse, loop,
  unrecovered_tool_error, step_limit, misread_result, wrong_result, unparseable_answer; fallback
  `unclassified`. `choose_primary()` is the only place that decides. Symptom signal: no_final_answer.
- Key rules: no_data_used = a required tool never CALLED (called-but-failed is a tool error, not a
  guess); tool_misuse = the registry/runner messages "unknown tool", "not allowed", "bad arguments";
  loop = same normalized call (whitespace, trailing ';') ≥ 3 times; unrecovered = that tool never
  succeeded after its last error; misread = the correct value is in the FINAL successful tool output
  (≤ 6 values, numbers within the task tolerance) and the answer could be read; wrong_result = the answer
  repeats a tool result (numbers compared at the answer's precision) and the correct value was not in the
  final output; unparseable = the evaluator's own `extract_number` refuses.
- Reuse, not a second parser: `evaluators.numbers_in()` and `allowed_difference()` (now also used by
  `check_number`).
- Warnings (never change the outcome): near_step_limit (≥ max_steps − 1), recovered_tool_errors,
  unfixed_tool_errors (added after real data showed an ignored calculator error in a passed run),
  llm_retries; for old runs with `retries=None` and more LLM calls than steps:
  unrecorded_retries_likely ("details unknown"), never "0 retries".
- Failure zoo (`tests/test_analysis.py`): scripted fixtures through the real runner, tools, DB and
  evaluator for every category, the unclassified fallback, priority, multiple signals, infra excluded,
  passed runs, warnings, the sloppy suite (4 × wrong_result) and historical re-analysis of the genuine
  v1 database. Mutation check: swapping two priorities makes 3 tests fail.
- Real data (copy of the user's results.db): 0 failures; warnings: shop-010 near_step_limit +
  recovered calculator errors, shop-009/010 unrecorded_retries_likely ("9 LLM calls for 8 steps").


**Step 8.1 Retry recording + schema migration 1 → 2: ✅ complete.**
- `RetryEvent(step_index, attempt, error_kind, status_code, waited_seconds, request_id, occurred_at,
  succeeded)`; `RunResult.retries`: `None` = not recorded (pre-Phase-8 runs), `[]` = recorded, none.
- Runner: every failed attempt that is followed by a wait and another try becomes an event; when the
  call ends, its events get `succeeded` (did the call finally work). Exhausted retries: attempts 1..n-1
  are events with `succeeded=False`, the last failure is the run error. Locally refused (budget)
  attempts are not events. `LLMError.request_id` added (Gemini mapping does not extract one yet → None).
- Storage schema **v2**: `MIGRATIONS[1]` = `ALTER TABLE run_records ADD COLUMN retries_recorded`
  (DEFAULT 0 = unknown for existing rows) + new `retries` table. Opening runs create (if new) + all
  migrations + new version in ONE transaction; failure → `ROLLBACK`, `StorageError("… nothing was
  changed")`, file stays v1. New databases go through the same path (identical schema, tested). Newer
  versions refused.
- Genuine v1 fixture: `tests/fixtures/results_v1.sql` + `results_v1_suites.json`, dumped from a database
  written by the Phase 7 code (`make_results_v1_fixture.py`, generated before the migration existed).
- Verified on a COPY of the user's real `results.db`: v1 → v2, both Gemini runs intact, retries shown
  as not recorded. The real file migrates automatically the first time it is opened.
- Notes: `docs/learning/phase-8-notes.md`.

**Phase 7 — Result storage: ✅ complete** (Steps 7.1, 7.2). Tests: **323 passed** (run by Claude;
19 new in 7.2 — user to confirm).

**Step 7.2 Queries, auto-save, results CLI: ✅ complete.**
- `ResultStore.list_suites(real_only=, limit=) -> [SuiteSummary]`: newest first (`ORDER BY started_at
  DESC`; timestamps stored in UTC so text order = time order); passed / failed / infra / skipped /
  requests counted by SQL (`LEFT JOIN` + `GROUP BY` + `SUM(outcome = 'passed')`). Tested to equal
  `compute_metrics()` for complete, repeated and incomplete suites.
- `task_history(task_id) -> [TaskHistoryEntry]`: every scheduled run of a task across suites, newest
  first, with config, model, prompt hash and **task version** (`task_hash`); skipped runs included
  (`UNION ALL`) with their reason.
- `resolve(prefix)`: short ids like git (`substr()`, not `LIKE`, so `%` / `_` stay plain text);
  unknown or ambiguous → `SuiteNotFoundError`.
- `save_with_recovery(suite, path, recovery_dir) -> SaveOutcome`: never raises; on any database
  failure it writes a JSON recovery copy and reports the error. Execution and persistence stay separate.
- `scripts/run_benchmark.py`: every finished suite is stored automatically (`--results-db`, default
  `data/results.db`). On failure: a WARNING that the results are still valid, the reason, the recovery
  file, the import command, and exit code 1. Never claims "Stored" unless the transaction committed.
- `scripts/results.py [--db]`: `list [--real] [--limit]`, `show <id>`, `compare <id> <id> ...`,
  `history <task_id>`, `import <files...>` (a duplicate prints "already stored", nothing changes).
- Report: new `Suite id` line.
- Fix (found by the user comparing the real runs 1×10 vs 3×10): an unfair comparison printed
  "NOT A FAIR COMPARISON" and then "differences reflect run-to-run variation only". Now, when the setup
  differs, the configuration line is information only ("no dimension changed either …" / "also
  changed: …") and never attributes the differences. New test; tests: **324 passed**.
- Trial (scratch DB): both real Gemini exports imported (`743cde41` 10×1, `0af951e0` 10×3), the same
  file again → "already stored"; `--compare` stored 2 scripted suites; `list` and `history shop-010`
  correct (6 runs, all passed, one task version).

**Step 7.1 Result storage (save/load): ✅ complete** Result storage (save/load): ✅ complete** (tests: **304 passed**; 26 new).
- `src/agentbench/storage.py`: `ResultStore(path=data/results.db)` — the only code that talks to the
  results DB (repository pattern). `save(suite) -> suite_id` in ONE transaction (`BEGIN IMMEDIATE` …
  `COMMIT`, `ROLLBACK` on any failure → `StorageError`, in-memory result untouched), `load(suite_id)`
  (lossless: `load(save(s)) == s`, validators run again), `exists()`. Errors: `StorageError`,
  `DuplicateSuiteError`, `SuiteNotFoundError`, `SchemaVersionError`.
- Schema v1 (`PRAGMA user_version = 1`), 7 tables: `suite_runs` (config as columns), `task_versions`
  (immutable task snapshots keyed by sha256 of the full definition; shared across suites, an edited task
  becomes a new row), `suite_tasks` (which version each suite scheduled, in order), `run_records`
  (PK `run_id`; FK (suite_id, task_id) → suite_tasks; UNIQUE (suite_id, task_id, repeat_index)),
  `steps` (tool call as optional columns, arguments as JSON), `checks`, `skipped_runs` (own table,
  mirrors `SkippedRun`). Indexes on `suite_runs.started_at`, `run_records.task_id`,
  `task_versions.task_id`. Foreign keys ON per connection; every value a `?` parameter.
- Opening: version 0 + empty file → create schema and version in one transaction; another version or a
  non-AgentBench file → `SchemaVersionError`.
- `SuiteResult.suite_id` (new, 32 hex). Old JSON exports without it get a stable id derived from their
  run ids, so the same file always maps to the same suite. Nested task ids that disagree are refused.
- Verified: the real 30-run Gemini export saved and loaded back identical (1 suite, 10 task versions,
  30 records, 165 steps, 90 checks).
- Fix (bug from Step 6.2, found by the user's test run): two JSON exports within the same clock tick got
  the same file name; mode "x" refused correctly but `export_json` crashed. Now it adds `_2`, `_3`, ...
  New test freezes the clock to force the collision (no longer timing-dependent). Tests: 304.
- Teaching demo: `docs/learning/sqlite_basics_demo.py` (students and marks: tables, JOIN, GROUP BY,
  foreign key, rollback, SQL injection, user_version). Notes: `docs/learning/phase-7-notes.md`.

**Phase 6 — Benchmark runner: ✅ complete** (Steps 6.1, 6.2, 6.3).

**Reliability run** (user ran, `gemini-3.5-flash-lite`, **3 repeats**): **30/30 passed, pass@3 10/10,
pass^3 10/10**; 170 requests (estimate 150, budget 200), 1,113 s, avg 5.5 steps / 5.7 LLM calls,
2,461 input tokens. Findings from the saved JSON:
- Very consistent: identical final answers and nearly identical tool sequences in every repeat.
- shop-009 (all 3) and shop-010 (2 of 3) made one more LLM call than steps: a request was retried
  (12 s gap instead of 6 s). The retried error is NOT recorded anywhere — a tracing gap.
- shop-010 used 8 of 8 steps in 2 of 3 runs; both times the model tried `round(16107.32)`, which the
  safe calculator rejects (a tool-usability finding), then recovered.
- Ceiling effect confirmed: the suite cannot separate configs for this model; harder tasks needed.
- The 5-requests-per-run estimate is low (actual 5.7).

**Step 6.3 Free-tier safety for real runs: ✅ complete.** Tests: **278 passed** (user-reported; 14 new).
- `src/agentbench/llm/pacing.py`: `Pacer` (≥ N s between request starts, shared by the whole suite),
  `RequestBudget` (HARD cap: refuses before sending, new error kind `budget_exhausted`),
  `RateLimitedLLM` (decorator: budget → pacing → inner LLM; the agent loop is unchanged).
- `benchmark.py`: `estimate_requests()` / `RequestEstimate` (typical = runs × 5, worst case =
  Σmax_steps × repeats × max_attempts, rough time); `run_suite(request_budget=, min_requests_to_start=)`;
  a task is not started if the remaining budget < ~5; circuit breaker on auth / quota_exhausted /
  budget_exhausted → all remaining runs skipped with the reason, `stop_reason` set, 0 further requests.
  Temporary errors (server, network, rate limit after retries) do not trip it.
- `runner.py`: a locally refused request (`NOT_SENT_KINDS`) is not counted in `llm_calls`.
- `SuiteResult` gained `request_budget`, `estimated_requests`, `stop_reason`; the report shows
  "Requests: N actual | estimate E | budget B" and "Stopped: …".
- `scripts/run_benchmark.py --agent gemini`: prints the estimate and exits with zero requests;
  `--yes` runs it; `--budget N` (default 80); pacing 6 s.
- `test_report.py`: the incomplete-suite test now expects the circuit breaker (shop-003..010 skipped).
- **First real full-suite run** (user ran, `gemini-3.5-flash-lite`, 1 repeat): **10/10 passed**
  (easy 2/2, medium 4/4, hard 4/4). **57 actual requests** (estimate 50, budget 80), avg 5.7 steps,
  avg 2,608 input / 145 output tokens per run, 35.1 s avg, 351 s total, 47 tool calls, 2 tool errors —
  both the model calling functions inside `calculator` (`datetime(...)`, `round(...)`), rejected by the
  safe calculator; the model recovered both times. shop-010 needed 8 of its 8 allowed steps.
  Saved: `results/shop_gemini-default_20261113T054832046291Z.json`.
- Interpretation (honest): one run, no repeats → says nothing yet about consistency (pass^k); 10/10
  suggests the suite may be too easy to separate stronger from weaker configs (ceiling effect).
  The ~5 requests/task estimate was low (actual 5.7).

**Step 6.2 Scripted agents + comparison + JSON export: ✅ complete.** Tests: **264 passed**
(user-reported; 16 new).
- `src/agentbench/suites/shop_agents.py`: scripted `careful` (correct SQL for all 10 tasks) and `sloppy`
  (same scripts except 4 deliberate traps) FakeLLM agents; SQL runs on the real DB. `scripted_config()`,
  `scripted_agent()`. Labelled "SCRIPTED AGENT (not a real AI)" in every report.
- `src/agentbench/report.py`: `format_report()`, `compare()`, `export_json()`, `load_json()`.
  Comparison separates CONFIG dimensions (provider, model, prompt hash, max attempts, pacing) from
  FAIRNESS dimensions (tasks fingerprint, dataset, repeats — must match). Prints "NOT A FAIR COMPARISON",
  "Changed dimension: X", a multi-change warning, or an incomplete-run warning. Config name is not a
  dimension. Export: `results/<suite>_<config>_<timestamp>.json`, opened with mode `"x"` (never
  overwrites); `load_json()` re-validates and ignores stored metrics; export → load is lossless.
- `SuiteResult` gained `tasks` (full definitions, must match `task_ids`), `dataset` (file SHA-256) and the
  `tasks_fingerprint` property. Saved runs can be re-graded with zero LLM calls (tested).
- `scripts/run_benchmark.py` (`--agent careful|sloppy`, `--compare`, `--repeats`, `--save`;
  `--agent gemini` deliberately refused until Step 6.3). User ran: careful **10/10**, sloppy **6/10**
  (shop-003, 004, 007, 009 failed), 4 rows `<- differs`, "Changed dimension: model"; `--save` wrote
  `results\shop_sloppy-script_20261113T050954008058Z.json`.
- Display fixes: `·` showed as `�` in the Windows console → `|`; column widths fit the longest value.

**Step 6.1 Suite runner + metrics: ✅ complete.** Tests: **248 passed** (user-reported; 20 new).
- `src/agentbench/benchmark.py`: `run_suite(tasks, config, make_llm, tools, suite_name=, repeats=)` —
  sequential, injected LLM factory `(task, repeat) -> LLMClient`, progress lines, every run kept.
- `src/agentbench/metrics.py`: `compute_metrics(suite) -> SuiteMetrics` — pass rate as passed/eligible
  (denominator always shown), by difficulty, averages over eligible runs, totals over all executed runs,
  tool calls/errors, most-failed checks, pass@k / pass^k (empirical, only tasks whose k repeats were all
  eligible). Tokens `None` when the provider reports none.
- Models: `Task.difficulty`; `AgentConfig` (provider fake|gemini, model, system_prompt, max_attempts,
  min_interval_seconds, auto `prompt_hash`); `RunRecord` (outcome passed|failed|infra_error, validated);
  `SkippedRun`; `SuiteResult` (`is_complete` = all scheduled runs executed and evaluated).
- Infrastructure error kinds (not agent failures): auth, quota_exhausted, rate_limit, server, network,
  bad_request, config, unknown. `invalid_response` and `max_steps` count as agent results.
- Shop tasks: explicit difficulty (2 easy, 4 medium, 4 hard).

**Phase 5 — Evaluators + Data Analyst benchmark: ✅ complete** (Steps 5.1, 5.2, 5.3).


**Step 5.3 Shop benchmark suite: ✅ complete.** Tests: **228 passed** (user-reported; 37 new).
- `src/agentbench/suites/shop.py`: `SHOP_TASKS` (10 tasks: 2 easy, 4 medium, 4 hard), `get_task()`,
  `shop_registry(db)` (exactly the advertised tools: `list_tables`, `describe_table`, `sql_query`,
  `calculator` — calculator verified to exist, the Phase 2 AST-based tool). All tasks: required
  `sql_query`, max 8 steps, answer format stated in the prompt. shop-009 ±0.05, shop-010 ±1.
- `tests/test_shop_suite.py`: independent reference SQL (different approach, e.g. NOT IN vs LEFT JOIN)
  agreed with all 10 proposed answers — no discrepancies; tie checks for the 5 "which X" tasks;
  the evaluator accepts every reference answer and rejects 7 trap answers; ids unique, required ⊆
  allowed ⊆ registered; end-to-end run with real tools + DB (good agent passes, INNER JOIN mistake
  completes but fails).
- `scripts/run_shop_task.py`: one task end to end (trace + evaluation). User ran: FakeLLM good → PASSED;
  `--mistake` → completed but FAILED (answer 0, expected 3); `--gemini shop-004` (gemini-3.5-flash-lite) →
  explored schema, joined order_items, avoided the never-ordered Smart Watch trap → PASSED, 5 LLM calls,
  33.2 s (no retries; free-tier latency).

**Step 5.2 SQL tools + shop database: ✅ complete.** Tests: **191 passed** (user-reported; 58 new).
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

**Step 5.1 Evaluators: ✅ complete.** Tests: **133 passed** (user-reported; 44 new).
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
| Answer key | Proven by independent reference SQL + tie checks in tests | A wrong key makes every score a lie |
| Benchmark data | Private generated DB | No contamination: answers exist nowhere online |
| Pass rate | passed / eligible; infra errors and skipped runs reported separately | An agent isn't failed for Google's quota |
| Suite execution | Sequential, LLM injected per run | Free-tier limits; scripted and real agents share one runner |
| Comparison fairness | Config dimensions vs. fairness dimensions (tasks fingerprint, dataset, repeats) | Only one variable may change; otherwise say so |
| Result export | JSON with full tasks, never overwrite; metrics recomputed on load | Free re-grading; files aren't trusted |
| Scripted agents | Careful/sloppy FakeLLM scripts, always labelled SCRIPTED | Test the pipeline for ₹0 without faking AI results |
| Real-run safety | Hard per-request cap + circuit breaker + `--yes` after an estimate | A free quota can never be overspent by accident |
| Result storage | Built-in sqlite3, normalized tables, repository class, one transaction per suite | No dependency, real SQL; nothing half-saved |
| Task history | Content-hashed immutable task versions per suite | Old results stay interpretable after task edits |
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
- [x] **Phase 5** — Evaluators: exact-match, contains, tool-usage; later LLM-as-judge
- [x] **Phase 6** — Benchmark runner: task suites, batch runs, metrics, agent configs + comparison;
  more realistic tools (SQL query over sample SQLite DB, date calculator, unit converter, file reader)
- [x] **Phase 7** — Storage: SQLite for runs & traces (adds `run_id`)
- [x] **Phase 8** — Failure analysis: categorize failures
- [ ] **Phase 9** — FastAPI backend: REST API over the framework and database
- [ ] **Phase 10** — Dashboard: React + TypeScript + Tailwind + Recharts
- [ ] **Phase 11** — Docker: package backend (and dashboard) for one-command start

Planned model additions (added only in their phase): token counts on `Step` (Phase 3),
`AgentConfig` (Phase 6), `run_id` (Phase 7).

## Next step
Benchmark v2, Step A.2 — harder suite `shop-hard` on the same shop.db (tasks designed before any real run, answers proven by independent SQL). Plan first; waiting for user approval.
Candidates noted earlier: record retried errors in traces, calculator `round()`, harder tasks,
estimate 6 requests per run.

# Phase 7 notes — storing results in SQLite

Warm-up first: `python docs/learning/sqlite_basics_demo.py` (students and marks, in memory).

## Why a database at all?
JSON files are loose papers in a drawer: fine for one run, useless for "all runs, newest first" or
"how did shop-010 do across every run?". A database is the filing cabinet with an index.

## The 9 concepts

| Concept | One line | In the demo | In AgentBench |
|---|---|---|---|
| Table / row / column | A sheet with fixed, typed columns; one row per item | `students`, `marks` | 7 tables in `storage.py` |
| Primary key | Uniquely identifies a row (a roll number) | `roll_no` | `suite_id`, `run_id`, `(run_id, step_index)` |
| Foreign key | A child row points to its parent; orphans are refused | `marks.roll_no` | `steps.run_id → run_records` |
| One-to-many | One parent, many children | a student → many marks | a suite → many records → many steps |
| Normalization | Each fact in ONE place, linked by keys | names only in `students` | config in `suite_runs`, not copied into every record |
| Transaction | All or nothing: `BEGIN` … `COMMIT` / `ROLLBACK` | Zoya's enrolment | one suite = one transaction |
| Parameterized query | Values go as `?`, never pasted into SQL text | the `' OR '1'='1` demo | every value in `storage.py` |
| Index | The back-of-the-book index for a column | `idx_marks_subject` | `run_records.task_id`, `suite_runs.started_at` |
| Schema version | A number in the file saying which table design it uses | `PRAGMA user_version` | version 1; anything else is refused |
| Repository pattern | One class owns all SQL; others call methods | — | `ResultStore.save()` / `.load()` |

## Design decisions (and why)

**Built-in `sqlite3`, no ORM.** No new dependency, and you see the real SQL. Because only `ResultStore`
knows about SQLite, switching to PostgreSQL later would change one file.

**Two database files.** `shop.db` is what the agent may read; `results.db` holds answers, traces and
scores. If they were one file, the agent's `sql_query` could read the expected answers. Separation is
security AND it prevents contamination.

**Task versions by content hash.** A task id alone is not enough: if someone changes shop-010's
tolerance next month, old results must still say which rule they were graded with. Each distinct
definition is stored once in `task_versions`, keyed by `sha256(definition)`. A suite points to the
exact versions it used (`suite_tasks`). Same content = same hash = stored once; edited content = new row.
The definition itself is stored as JSON because it is an immutable snapshot of a model that will gain
fields over time — we never query inside it, we only load it back exactly.

**Three ids, three meanings.** `suite_id` = one benchmark execution. `run_id` = one task execution
inside it (already existed). `task_id` = the benchmark task. `task_hash` = one version of a task.

**Skipped runs in their own table.** A skipped run has no trace, no status, no duration, no evaluation.
Forcing it into `run_records` would make most columns nullable and every query would need
"…AND not skipped". It mirrors the existing `SkippedRun` model instead.

**Tool calls as optional columns of `steps`.** A step has 0 or 1 tool call (one-to-one), so no extra
table. A CHECK rule makes sure "no tool name" means "no arguments, output or error" either. Arguments
are free-form (any JSON), so they are stored as JSON text.

**One transaction per suite.** About 300 rows for a 30-run suite. A crash at row 150 without a
transaction would leave a half suite that the dashboard shows as "15 runs" — a lie. With it: nothing.

**Persistence is not execution.** A disk error while saving raises `StorageError`; the benchmark
result in memory is untouched, so it can still be exported to JSON. A save failure never turns
passed runs into failures, and the program never claims "saved" when it wasn't.

**Old JSON exports.** Files from before `suite_id` existed get an id derived from their run ids
(which are unique), so importing the same file twice always gives the same suite id — no duplicate.

## Things that surprised us
- SQLite's foreign keys are **off by default**, per connection. Forget `PRAGMA foreign_keys = ON`
  and orphans are silently accepted.
- `PRAGMA` cannot take `?` parameters. We only ever put our own constant (`SCHEMA_VERSION`) there.
  Table names can't be parameters either; tests use an allowlist (`TABLES`) before building SQL.
- A test bug: `model_copy()` is a SHALLOW copy. Changing a nested object in the copy changed the
  shared test fixture too. Fixed with `model_copy(deep=True)`.

## Self-check
1. Why do `steps` live in their own table instead of inside the `run_records` row?
2. A save crashes after 5 of 10 records. What does the database contain? Why?
3. Why is `f"... WHERE model = '{model}'"` dangerous even though WE write that code?
4. Why must `results.db` never be the same file as `shop.db`?
5. shop-010's tolerance is changed. How can you still tell which tolerance an old run was graded with?

## Step 7.2 — asking questions with SQL

**Counting in SQL instead of Python (`list_suites`).**
```sql
SELECT s.suite_id, COALESCE(SUM(r.outcome = 'passed'), 0) AS passed, ...
FROM suite_runs s LEFT JOIN run_records r ON r.suite_id = s.suite_id
GROUP BY s.suite_id ORDER BY s.started_at DESC
```
- `outcome = 'passed'` is 1 or 0, so `SUM` counts the passes.
- `LEFT JOIN` keeps a suite even if it has no records (all skipped); `COALESCE` turns its NULL sum into 0.
- A test checks these SQL counts against `compute_metrics()` — two independent methods must agree,
  like the reference SQL that proved the shop answer key.

**Time order = text order.** Timestamps are stored as UTC ISO text (`2026-11-13T06:25:18+00:00`), so
sorting the strings sorts by time. Mixing time zones would break that, so `_iso()` converts to UTC.

**`UNION ALL` (`task_history`).** Executed runs and skipped runs live in different tables; `UNION ALL`
stacks the two result lists into one, so a skipped run still appears in a task's history.

**Short ids.** `resolve("0af9")` finds the one suite starting with those characters (like git).
`substr(suite_id, 1, ?) = ?` instead of `LIKE ? || '%'`, because in LIKE the characters `%` and `_`
are wildcards — user input must stay plain text.

**Persistence failure ≠ benchmark failure (`save_with_recovery`).** The benchmark already ran; a
broken disk must not change that. So the save never raises: it returns `saved=False`, the error, and a
JSON recovery copy. The script prints a WARNING, the import command, and exits with code 1 — and
never prints "Stored" for a transaction that didn't commit.

## Self-check (7.2)
6. Why `LEFT JOIN` and not `JOIN` in `list_suites`? Which suite would disappear with `JOIN`?
7. Why is `substr()` safer than `LIKE` for matching a short id typed by a user?
8. The disk is full at the end of a 20-minute Gemini run. What does the user see, and what is lost?

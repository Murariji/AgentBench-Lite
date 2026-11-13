# Phase 8 notes — failure analysis

## The concepts

**Failure taxonomy.** A fixed list of failure categories with clear definitions, so every failed run
gets exactly one primary category and counts can be compared across runs. Like a doctor's list of
diagnoses: "sick" is not useful, "flu" is.

**Rule-based classification vs. an LLM judge.**
| | Rules (our choice) | LLM judge |
|---|---|---|
| Cost | ₹0 | API requests for every run |
| Repeatable | always the same verdict | can change between calls |
| Explains itself | evidence: step numbers, tool names | a written opinion |
| Limits | sees WHAT happened, not WHY | can be wrong itself; still not the model's real "reason" |
Rules describe **observable evidence and likely failure patterns**. They never claim to know what the
model was "thinking".

**Evidence and signals.** Every category is backed by facts from the trace ("step 3: sql_query error
'no such column'; no later successful sql_query"), like the `reason` on every evaluation check.

**Primary cause vs. symptoms.** One run can show several problems. A loop that runs out of steps has
the loop as its cause and the step limit as a symptom. A fixed priority order picks the primary
category; everything else stays visible as additional signals.

**Near-miss warnings.** A passed run can still be risky: shop-010 passed but used 8 of its 8 steps.
Warnings (near the step limit, recovered tool errors, retried requests) never turn a pass into a fail;
they show where the next failure will probably come from.

**Database migrations.** Changing the table design of a database that already holds data, without
losing it: the code reads `PRAGMA user_version` and applies each step "N → N+1" in order.

**Historical re-analysis.** Categories are computed from stored traces when read, never saved. Better
rules later = every old run re-analysed for free, with zero API calls.

## Step 8.1 — recording retries + migration 1 → 2

**The gap (found in the real Gemini runs):** shop-009 and shop-010 made one more LLM call than they had
steps, so a request had failed and been retried — but nothing recorded it.

**`RetryEvent`** (one per failed request that was retried):
```
step_index, attempt, error_kind, status_code, waited_seconds, request_id, occurred_at, succeeded
```
- `attempt` 1 = the first try of that call failed. If all 3 attempts fail, attempts 1 and 2 are retry
  events (`succeeded=False`) and the 3rd failure is the run's error (no retry followed it).
- `succeeded` = did that LLM call EVENTUALLY work.
- `request_id`: `LLMError` can now carry one, but our Gemini error mapping does not extract one yet, so
  it is `None` for Gemini today — stated, not invented.

**`RunResult.retries`: `None` vs `[]`** — the most important detail of this step:
| Value | Meaning |
|---|---|
| `None` | NOT RECORDED: the run happened before Phase 8. Unknown. |
| `[]` | Recorded, and no request needed a retry. |
| `[...]` | Recorded retries. |
Showing old runs as "0 retries" would be a false history. Your two real Gemini runs DID have retries.

**The migration (schema 1 → 2):**
```sql
ALTER TABLE run_records ADD COLUMN retries_recorded INTEGER NOT NULL DEFAULT 0 ...;  -- old rows: 0 = unknown
CREATE TABLE retries (...);
PRAGMA user_version = 2;
```
- All in ONE transaction: if any statement fails, `ROLLBACK` undoes even the `ALTER TABLE`; the file
  stays version 1 with every row (tested by appending a failing statement to the migration).
- A new database runs the SAME path (version-1 schema, then every migration), so fresh and upgraded
  databases are identical (tested column by column).
- The version-1 schema text is never edited again: databases in the wild were created with it.
- **Genuine fixture:** `tests/fixtures/results_v1.sql` was dumped from a database written by the real
  Phase 7 code before the migration existed (`make_results_v1_fixture.py` explains how). The test
  upgrades it and checks every stored suite loads back identical.

## Self-check (8.1)
1. Why is `retries = None` for old runs more honest than `[]`?
2. All 3 attempts of a call fail. How many RetryEvents are there, and why not 3?
3. The migration's `CREATE TABLE` succeeds but the next statement fails. What is in the file afterwards?
4. Why does a brand-new database also go through the migration instead of a separate "version 2" schema?

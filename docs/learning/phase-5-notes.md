PHASE 5 NOTES - EVALUATION
AgentBench-Lite | Step 5.1 completed 2026-11-12
=====================================================================

Goal: judge runs. Phase 4 = EXECUTION (what did the agent do?).
Phase 5 = EVALUATION (was it right, and did it follow the rules?).


=====================================================================
PART 1 - EXECUTION vs EVALUATION (the key architecture idea)
=====================================================================

             Execution (runner.py)        Evaluation (evaluators.py)
question     what happened?               was it correct?
output       RunResult                    EvaluationResult
words        completed/max_steps/error    passed True/False + checks
LLM needed?  yes (costs quota)            no (free, instant)
analogy      the match + camera           the third umpire

linked by    run_id  (RunResult.run_id == EvaluationResult.run_id)

Why separate:
  - re-grade old runs for FREE when rules improve (no new API calls)
  - test each part alone (evaluators use hand-made RunResults)
  - one run, many judges
  - dashboard: efficiency metrics vs correctness metrics
  - single responsibility

"completed" != "correct": a run can finish with a wrong answer,
or a right answer without using the required tool (a lucky guess).


=====================================================================
PART 2 - CHECKS AND THE VERDICT
=====================================================================

status          run must be "completed"
answer:<type>   exact | contains | number   (task.answer_type)
required_tools  each listed tool needs >= 1 SUCCESSFUL call
                (only added if task.required_tools is not empty)

Every check has: name, passed, reason (always explained).
Verdict: passed = all(checks). No score, no averaging:
an average gives a lucky guess and a wrong answer the same 67%.
The model validator makes a lying verdict impossible.


=====================================================================
PART 3 - ANSWER MATCHING
=====================================================================

exact     normalise (case, spaces, quotes, final . or !) then compare
contains  expected must appear as WHOLE WORDS ("Delhi" not in "Delhiwala")
number    1. remove currency (fixed list: ₹ $ Rs. INR rupees ...)
          2. commas only as thousands separators: 1,240 / 12,40,000
             ("1,5" refused - could be European decimal)
          3. which number?
               only one             -> it
               marker = is answer: total:  -> first number after LAST marker
               all the same         -> it
               otherwise            -> FAIL "ambiguous" (never guess)
          4. Decimal, not float:  0.1 + 0.2 = 0.30000000000000004 (float)
                                  Decimal('0.1') + Decimal('0.2') = 0.3
          5. pass if |answer - expected| <= max(abs_tol, rel_tol*|expected|)
             defaults 0 and 0 = exact

Correction made while testing: 0.15 * 840 is exactly 126.0 in Python.
The float problem is real, but that was a bad example. Tests caught it.


=====================================================================
PART 4 - LIMITATIONS (be honest in interviews)
=====================================================================

Deterministic checks compare text/numbers, not MEANING:
  "New Delhi" vs "Delhi"           -> mismatch
  "Not Delhi, it's Mumbai"         -> contains-check PASSES (wrong!)
  open-ended answers (summaries)   -> cannot be graded
Fix would be LLM-as-judge -> costs quota -> out of scope (₹0).
Mitigation: tasks with crisp answers + "reply with the answer only".


=====================================================================
PART 5 - DESIGN DECISIONS
=====================================================================

allowed_tools (Phase 4)  DURING the run: what the agent CAN use
required_tools (new)     AFTER the run: what it MUST have used
forbidden_tools          NOT added: leaving a tool out of allowed_tools
                         already blocks it and records the attempt.
Task without expected_answer -> answer check fails ("cannot be graded"),
never a silent pass.


=====================================================================
PART 6 - SELF-CHECK
=====================================================================

1. Why can a run be "completed" but still fail evaluation?
2. Why is re-grading old runs free?
3. Why no average score?
4. "Revenue was 1,200 in Jan and 1,500 in Feb, so growth is 25%"
   -> which rule, which number?
5. Why is "1,5" refused instead of read as 15 or 1.5?
6. Why Decimal instead of float?



=====================================================================
STEP 5.2 - SAFE SQL TOOLS + SHOP DATABASE   (completed 2026-11-12)
=====================================================================

WHY IT MATTERS
  The model WRITES SQL and we RUN it. Its SQL depends on text it reads,
  so it can be tricked (prompt injection). Treat it as untrusted input.

THREATS                                  STOPPED BY
  change/destroy data (DELETE, DROP)     read-only file, query_only, authorizer
  read OTHER files (ATTACH 'x.db')       authorizer + 0 attached DBs
  run native code (load_extension)       extensions off + authorizer
  freeze (infinite recursion, joins)     progress-handler time limit
  eat memory (randomblob(1e9))           size limits
  burn tokens (SELECT * huge)            50 rows, 200-char cells, 4000 chars
  sneak a 2nd statement ("; DROP")       sqlite3 allows one statement only
  switch protection off (PRAGMA)         authorizer denies PRAGMA

AUTHORIZER = a guard who opens the bag and checks each item.
  SQLite asks our function before EVERY action ("may I read
  fruits.price?", "may I DELETE?", "may I ATTACH?").
  ALLOWLIST: SELECT, READ, FUNCTION, RECURSIVE. Everything else DENY.
  Allowlist > blocklist: unknown actions are denied by default.

REGEX IS NOT THE BOUNDARY
  "WITH x AS (SELECT 1) DELETE FROM orders" starts with WITH, so it
  PASSES our text check - and SQLite still blocks it. Tests call
  db._run() (skips the text check) to prove the engine alone is safe.
  Every attack test compares the DB file's SHA-256 before/after.

TIME LIMIT IS APPROXIMATE
  the progress handler runs every 1000 SQLite steps, not every ms.

SAFE DB BUILD
  refuse if the file exists (overwrite=True / --rebuild to replace);
  write to a temp file, then os.replace (atomic) - a crash never leaves
  a half-built shop.db.

DATASET (fixed seed 2026): 30 customers / 7 cities, 15 products /
  4 categories, 150 orders Jan-Jun 2026, 369 order items.
  Traps: multi-product orders, 3 customers with no orders (LEFT vs
  INNER JOIN), 2 products never ordered. Note: 4 cities tie at 5
  customers -> avoid ambiguous "which city has the most" questions.

LIMITATIONS: not an OS sandbox; SQLite bugs; all data readable;
  approximate timeout; can't stop WRONG queries (that's the benchmark).

THE TEMP-FOLDER ERROR
  58 tests: "ERROR at setup ... PermissionError: Access is denied:
  ...\Temp\pytest-of-<user>". Cause: Windows folder permissions,
  most likely broken by Claude's sandboxed test run.
  ERROR at setup = test never started (environment problem)
  FAILED         = test ran, an assertion was wrong (code problem)
  Fix: pyproject addopts "--basetemp=.pytest_tmp" (inside the project,
  git-ignored, emptied every run).

SELF-CHECK
  1. Why is the model's SQL untrusted even in our own agent?
  2. Why isn't a fixed path in our code enough to stop reading other files?
  3. Allowlist vs blocklist - which is safer and why?
  4. If the SELECT text check is bypassed, what still stops DELETE?
  5. "ERROR at setup" vs "FAILED" - what does each tell you?

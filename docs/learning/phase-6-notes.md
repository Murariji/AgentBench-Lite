PHASE 6 NOTES - BENCHMARK RUNNER
AgentBench-Lite | Step 6.1 completed 2026-11-12
=====================================================================

Goal: from "one task, one run" to "a whole suite, a report card".

STEP 6.1 - SUITE RUNNER + METRICS
---------------------------------------------------------------------
run_suite(tasks, config, make_llm, tools, suite_name, repeats)
  for each task, for each repeat (SEQUENTIAL):
      run = AgentRunner(make_llm(task, repeat), ...).run(task)
      infra error?  -> RunRecord(outcome="infra_error", evaluation=None)
      otherwise     -> evaluate -> RunRecord(outcome="passed"/"failed")
  make_llm = dependency injection: scripted FakeLLM per task, or the
  same Gemini client every time. The runner never knows which.

NOTHING DISCARDED: every scheduled run is a RunRecord or a SkippedRun.
RunRecord validator: infra_error has no evaluation; passed/failed has
THIS run's evaluation; outcome agrees with evaluation.passed.

AGENT FAILURE vs INFRASTRUCTURE FAILURE
  infra (not the agent's fault): auth, quota_exhausted, rate_limit,
      server, network, bad_request, config, unknown
  agent results: completed, max_steps, invalid_response (bad reply)
  Example: 10 scheduled, 5 passed, 2 failed, 3 infra
      -> pass rate 5/7 (71.4%), infra 3, suite INCOMPLETE
  Always show the denominator. Never call a partial suite complete.

METRICS
  averages  over ELIGIBLE runs (the agent's real behaviour)
  totals    over ALL executed runs (quota and time were still spent)
  tokens    None (not 0) when the provider reports none

pass@k vs pass^k (k repeats per task)
  A: pass pass   B: pass fail   C: fail fail   D: pass NETWORK
  pass@2 = 2/3  (A, B can solve it)      D excluded (not all eligible)
  pass^2 = 1/3  (only A is reliable)
  For a real product, pass^k matters more: right 2 of 3 times isn't
  reliable.

AgentConfig.prompt_hash = first 12 chars of sha256(system_prompt),
  always recomputed (can't be faked) - same hash = same prompt.

SELF-CHECK
  1. Why is a quota error not an agent failure?
  2. Why are totals over ALL runs but averages over eligible runs?
  3. Explain pass@k vs pass^k with your own example.
  4. Why is make_llm a function instead of one LLM object?

==================================================================
STEP 6.2 - SCRIPTED AGENTS, COMPARISON, JSON EXPORT
==================================================================
SCRIPTED AGENTS (suites/shop_agents.py)
  careful: correct SQL for all 10 tasks          -> 10/10
  sloppy : same, but 4 deliberate traps           -> 6/10
           (shop-003, 004, 007, 009 fail)
  Their SQL really runs on shop.db, but the answers are written in
  advance: ZERO intelligence. Purpose: test the pipeline for free.
  Every report says "SCRIPTED AGENT (not a real AI ...)".

FAIR COMPARISON (report.compare)
  CONFIG dimensions   : provider, model, prompt hash, max attempts, pacing
  FAIRNESS dimensions : tasks fingerprint, dataset, repeats (MUST match)
  fairness differs  -> "NOT A FAIR COMPARISON"
  one config change -> "Changed dimension: model"
  several changes   -> WARNING: cannot attribute the difference
  The config NAME is only a label, not a dimension.

FINGERPRINTS
  dataset           = sha256 of the database file
  tasks_fingerprint = sha256 of the FULL task definitions
                      (prompt, answer, tolerance, tools, max steps)
  Change one tolerance -> different fingerprint -> not comparable.

JSON EXPORT
  results/<suite>_<config>_<timestamp>.json, open mode "x"
  ("x" = create only; never overwrites an old result)
  load_json() validates again and IGNORES stored metrics
  (derived data is recomputed, never trusted from a file).
  Full tasks are saved -> old runs can be RE-GRADED with 0 LLM calls.

SELF-CHECK
  1. Why does the sloppy agent's 6/10 say nothing about AI ability?
  2. Two runs have different tasks fingerprints. Can you compare them?
  3. Why open the export file with "x" instead of "w"?
  4. Why recompute metrics on load instead of reading them from JSON?

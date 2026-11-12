PHASE 4 NOTES - THE AGENT LOOP
AgentBench-Lite | completed 2026-11-12
=====================================================================

Goal: connect everything. Task in -> agent thinks, uses tools, repeats
-> RunResult out, with every step recorded in a Trace.

Real run (gemini-3.5-flash-lite):
    Step 0: calculator(0.15 * 840) -> 126      tokens in 253
    Step 1: word_count(the quick brown fox) -> 4   tokens in 289
    Step 2: calculator(126 + 4) -> 130         tokens in 322
    Step 3: final answer: 130                  tokens in 355
    4 LLM calls, 7.12 s. Input tokens grow each step = history resent.


=====================================================================
PART 1 - CONCEPTS
=====================================================================

ReAct loop      Reason + Act: model reasons, asks for a tool, OUR code
                runs it, result goes back, repeat until final text.
3 endings       completed (final text) | max_steps (time limit) |
                error (unrecoverable LLM problem)
"completed"     means the agent FINISHED, not that it was RIGHT.
                Correctness = Phase 5 evaluator.
Tool error      NOT a crash: sent back as a tool message with
                is_error=True so the model can self-correct.
Dependency      The runner is GIVEN its llm, tools, sleep and clock.
injection       Tests pass FakeLLM + FakeSleep -> free, instant, offline.
FakeLLM         a crash-test dummy: scripted, no intelligence. It tests
                OUR machinery. Real behaviour needs a real model
                (Gemini, or Ollama locally).


=====================================================================
PART 2 - ERROR & QUOTA POLICY (zero budget)
=====================================================================

kind              example                     action
auth              401/403, missing key        stop now
rate_limit        429 per-MINUTE (req/tokens) wait, bounded retry
quota_exhausted   429 per-DAY, or 0 quota     stop (resets tomorrow)
server            500/503                     bounded retry
network           offline, timeout            bounded retry
bad_request       400/404 (wrong model)       stop
invalid_response  empty reply                 stop
unknown           anything else               stop (safe default)

Backoff         wait 1s, 2s, 4s... (doubles), capped at 30s.
Retry-After     if Google says "wait 34s", wait exactly that;
                if it asks for > 60s, stop instead of hanging.
Bounded         max 3 attempts per call; per run at most
                max_steps x max_attempts calls (10 x 3 = 30).
SDK retries     switched OFF (attempts=1) so no hidden requests;
                RunResult.llm_calls counts every real request.
Broken task     unknown tool in allowed_tools -> error before ANY call.


=====================================================================
PART 3 - allowed_tools
=====================================================================

None        -> all registered tools on the menu
[]          -> no tools at all
["lookup"]  -> only those; asking for another -> tool error
               "not allowed" (Phase 8: "wrong tool" failure)


=====================================================================
PART 4 - TESTS (tests/test_runner.py, 19 tests, FakeLLM only)
=====================================================================

happy paths, multi-tool, tokens, JSON round trip, step limit,
tool-error recovery, allowed_tools, config error, 503 retry,
network retry, bounded backoff [1.0, 2.0], 401 stop, daily quota
stop, Retry-After respected, too-long Retry-After stops, LLM bug.
llm.remaining proves no extra calls were made.
Result: 89 passed.


=====================================================================
PART 5 - SELF-CHECK
=====================================================================

1. Name the 3 ways a run can end.
2. Why does a tool error NOT stop the run?
3. Why is "completed" not the same as "correct"?
4. 429 per-minute vs 429 per-day: what does the runner do for each?
5. What is the most API calls one run can ever make, and why?
6. Why do tests pass a FakeSleep instead of time.sleep?

# Benchmark v2 notes (Steps A.1 – A.4)

Why this exists: real Gemini runs passed 40 of 40, so the suite cannot separate configurations
(ceiling effect), and the failure analyser has only been proven on scripted fixtures. Plan (user's
decision): A.1 tool versions → A.3 calculator fix + measurement → A.2 harder suite → A.4 a few real
runs, gradually, within the free quota → Phase 9.

## Step A.1 — tool versions in the fingerprint

**The problem.** Comparisons checked tasks, dataset and repeats — but not the tools. After changing the
calculator, two runs would have looked like "no configuration dimension changed".

**What a tool is, to an agent — two layers:**
| Layer | What it is | How we track it |
|---|---|---|
| Contract | what the MODEL reads: name, description, parameter schema | automatic fingerprint (sha256 of canonical JSON) |
| Behaviour | what the CODE does (e.g. rejects `round()`) | a declared `version` (whole number, starts at 1) |

**Why declared, not hashed?** Hashing source code changes with every comment and formatting edit, and
misses changes inside helper functions. So the developer declares a new version — and tests enforce it.

**Canonical JSON.** One fixed text form: sorted keys, no spaces, real Unicode.
`{"b":1,"a":2}` and `{"a":2, "b":1}` become the same text, so they get the same hash on every machine.

**Explicit versions only.** `Tool.version` has no default. `ToolRegistry.register()` refuses a tool
without a whole-number version >= 1 (`True`, `"1"`, `1.5`, `0` are refused too).

**Snapshot + fingerprint.** `SuiteResult.tools` stores every `ToolSpec` (name, version, description,
parameters); `tools_fingerprint` hashes them all. So a comparison can say "calculator v1 -> v2", not
just "different".

**Same / changed / unknown.**
| Situation | Comparison says |
|---|---|
| same fingerprint | nothing extra |
| different | "Changed dimension: tools" + per tool: "calculator v1 -> v2", or "contract changed with the SAME version" (an undeclared change!) |
| one side not recorded | "WARNING: tools were not recorded … unknown, not assumed identical"; it never claims "run-to-run variation only" |

Tools are a CONFIGURATION dimension (like the model): Step A.3 changes them on purpose to measure the effect.

**Old runs are not backfilled.** Your Gemini runs almost certainly used calculator v1 — but "almost
certainly" is not recorded evidence. They stay "not recorded".

**Tripwires.** Tests pin today's contract fingerprints and representative calculator-v1 behaviours
(`round(16107.32)` → "unsupported syntax: Call", `2416098 / 150` → `16107.32`, …).
Limit: behaviour pins cover only the listed cases; they cannot detect every possible change in meaning.
Step A.3 will break the calculator pins ON PURPOSE — forcing version 2 and new pins.

**Migration 2 → 3** (one transaction, rolled back on failure): `suite_runs.tools_recorded` (DEFAULT 0 =
unknown for existing suites), `tool_versions` (one row per distinct spec, by hash), `suite_tools`.
Tested on genuine v1 AND v2 databases (`tests/fixtures/results_v1.sql`, `results_v2.sql`, each written by
the real code of its time).

## Self-check (A.1)
1. Only the calculator's description changed, same code. Why can two runs still not be compared as "same tools"?
2. Why does `Tool` have no default version?
3. What does "contract changed with the SAME version" tell you, and why is it a warning sign?
4. Why does an unknown tools record block the sentence "differences reflect run-to-run variation only"?
5. Which tests will fail in Step A.3, and why is that the intended outcome?

## Step A.3 — calculator version 2 (safe functions + honest rounding)

**Why.** In 3 of 4 real shop-010 runs Gemini tried `round(16107.32)`; v1 refused every function call,
the model wasted a step recovering, and runs used 7–8 of 8 steps. The tool was harder to use than needed.

**The allowlist.** Exactly `round`, `abs`, `min`, `max`, called plainly. Checked in this order, BEFORE
any argument is calculated: is it a plain name? is it allowed? no keywords? no `*`? right number of
arguments? Only then are the arguments evaluated (with the same safe rules). So `max(1/0, ... x21)` is
refused for its size without doing any division.

**Rounding — why not Python's `round()`:**
```
round(2.5)       -> 2      ties go to the EVEN number ("banker's rounding")
round(2.675, 2)  -> 2.67   2.675 is stored in binary as 2.67499999999999982...
```
**Our rule:** half away from zero, computed with `Decimal` and `ROUND_HALF_UP`
(in Python's decimal module, ROUND_HALF_UP means ties go AWAY from zero: -2.5 -> -3).
**Conversion rule:** int -> exact; float -> its SHORTEST printed form (`repr(2.675) == "2.675"`), then
`Decimal("2.675")`. `Decimal(2.675)` (from the binary value) would keep the binary error and give 2.67.
Plain arithmetic stays float, exactly as in v1 (`2416098 / 150` is still `16107.32`).

**Behaviour history (the tripwire pins):**
| Expression | v1 | v2 |
|---|---|---|
| `2416098 / 150` | 16107.32 | 16107.32 |
| `round(16107.32)` | unsupported syntax: Call | 16107 |
| `round(2.5)` | unsupported syntax: Call | 3 |
| `abs(-3)` | unsupported syntax: Call | 3 |
| `__import__("os")` | unsupported syntax: Call | function '__import__' is not allowed; allowed: abs, max, min, round |
| `math.floor(2.5)` | unsupported syntax: Call | only these functions can be called: abs, max, min, round |
| `2 ** 101`, `1 / 0` | refused | refused (unchanged) |

**The tripwires worked:** changing the calculator made 1 contract pin and all 7 v1 behaviour pins fail,
forcing version 2 and new pins. Only the calculator's contract changed — the SQL tools kept theirs.

**Measuring honestly (`results.py measure shop-010`).**
- Groups by (provider, model, tools): my first version grouped by tools only and put a SCRIPTED agent's
  column (4 calls by script) next to real Gemini runs (8.25 calls) — that would have been a fake
  improvement. Caught on a trial copy; fixed; a mutation check proves the tests catch it.
- Before: 4 Gemini runs with tools "unknown" (not recorded). After: up to 3 new runs with calculator v2.
- Infrastructure errors and skipped runs are counted apart, never as wrong answers.
- Limits it always prints: tiny samples (exploratory, not proof); unknown baseline; behaviour AND
  description changed together; the provider's model can change between days.
- Budget: hard cap 30. The generic estimate says ~15 (5 per run) but shop-010 has needed 7–9 per run;
  if the cap is reached, the cut repeat is "stopped by budget" and the report says INCOMPLETE.

**Known limitation:** results smaller than about 0.0001 print in scientific notation (`2e-10`), as all
floats have since v1. No benchmark task produces such values.

## Self-check (A.3)
6. Why does `round(2.5)` give 2 in Python, and why would that confuse an agent's answer?
7. Why must argument counts be checked BEFORE the arguments are calculated?
8. Why is `Decimal(repr(x))` used instead of `Decimal(x)` for floats?
9. Why would grouping `measure` by tools only have produced a misleading result?
10. The 3rd repeat is stopped by the budget. How is it counted, and what does the report say?

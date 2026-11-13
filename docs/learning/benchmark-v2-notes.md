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

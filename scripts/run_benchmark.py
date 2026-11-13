"""Run the whole shop benchmark suite and print a report.

    python scripts/run_benchmark.py --agent careful          # scripted agent, expected 10/10 (free)
    python scripts/run_benchmark.py --agent sloppy           # scripted agent with 4 trap mistakes (free)
    python scripts/run_benchmark.py --compare                # careful vs sloppy, side by side (free)
    python scripts/run_benchmark.py --agent sloppy --save    # also export JSON to results/
    python scripts/run_benchmark.py --agent gemini           # REAL Gemini: prints the estimate, sends NOTHING
    python scripts/run_benchmark.py --agent gemini --yes     # REAL Gemini: actually runs (free tier)
    python scripts/run_benchmark.py --agent gemini --tasks shop-010 --repeats 3 --budget 30   # only chosen tasks
    python scripts/run_benchmark.py --suite shop-hard --compare                  # the harder suite (scripted, free)

Real runs: >= 6 s between requests, a hard request budget (--budget, default 80) and a
circuit breaker that stops the suite on auth / quota errors.

Every finished suite is stored automatically in data/results.db (see scripts/results.py).
If that save fails, the result is NOT lost: a JSON recovery copy is written to results/.
"""

import argparse
import sys

from agentbench.report import compare, export_json, format_report
from agentbench.runs import (DEFAULT_BUDGET, GEMINI_PACING_SECONDS, RunRequestError, execute_plan,
                             gemini_client, gemini_config, plan_run, scripted_parts)
from agentbench.storage import DEFAULT_RESULTS_DB, save_with_recovery
from agentbench.suites import SUITES

# The safety logic (validation, registration guard, estimate, Gemini setup, budget, pacing) lives in
# agentbench/runs.py, shared with the web API, so both always follow the same rules.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=["careful", "sloppy", "gemini"], default="careful")
    parser.add_argument("--compare", action="store_true", help="run careful and sloppy, compare them")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--save", action="store_true", help="export JSON results to results/")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="hard cap on real requests")
    parser.add_argument("--yes", action="store_true", help="confirm a REAL (quota-using) run")
    parser.add_argument("--results-db", default=str(DEFAULT_RESULTS_DB), help="where runs are stored")
    parser.add_argument("--tasks", nargs="+", metavar="TASK_ID", help="run only these tasks, e.g. shop-010")
    parser.add_argument("--suite", choices=sorted(SUITES), default="shop", help="which task suite (default: shop)")
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.budget < 1:
        parser.error("--budget must be at least 1")
    real = args.agent == "gemini" and not args.compare
    try:
        # Validation + registration guard (incl. grading probes) + estimate - BEFORE any request.
        plan = plan_run("gemini" if real else "careful", args.suite, args.tasks, repeats=args.repeats,
                        budget=args.budget)
    except RunRequestError as exc:
        parser.error(str(exc))
    tasks, guard = plan.tasks, plan.guard

    if real:
        # The estimate comes FIRST; without --yes we stop here with zero API calls.
        print("=== REAL Gemini run (uses free-tier quota) ===")
        print(f"Suite      : {args.suite}")
        print(f"Tasks      : {', '.join(t.id for t in tasks)}")
        print(f"Registered : {guard.line()}")
        print(plan.estimate.describe())
        print(f"Pacing     : at least {GEMINI_PACING_SECONDS:.0f} s between requests")
        if guard.blocks_real_runs:
            print("\nREFUSED: this suite differs from its registration, so a real run would not measure the "
                  "registered benchmark. Nothing was sent. Register a new version instead "
                  "(python scripts/register_suite.py <suite> --version N).")
            raise SystemExit(1)
        if not args.yes:
            print("\nNothing was sent. Add --yes to start this run.")
            raise SystemExit(0)
    elif guard.blocks_real_runs:
        print(f"WARNING (scripted run, continuing): {guard.line()}")

    if real:
        client = gemini_client()     # only now: every check above has passed
        print(f"\n=== running {args.suite} suite with REAL {client.name} ===")
        suites = [execute_plan(plan, gemini_config(client.model), lambda task, repeat: client)]
    else:
        suites = []
        for kind in (["careful", "sloppy"] if args.compare else [args.agent]):
            print(f"\n=== running {args.suite} suite with the {kind} SCRIPTED agent ===")
            config, make_llm = scripted_parts(kind)
            suites.append(execute_plan(plan, config, make_llm))

    all_stored = True
    for suite in suites:
        print("\n" + format_report(suite))
        if args.save:
            print(f"\nSaved: {export_json(suite)}")
        # Persistence is reported SEPARATELY: a failed save never changes the benchmark result.
        outcome = save_with_recovery(suite, args.results_db)
        if outcome.saved:
            print(f"Stored     : {args.results_db} (suite id {suite.suite_id[:8]})")
        else:
            all_stored = False
            print(f"\nWARNING: the benchmark finished, but saving it to {args.results_db} FAILED.\n"
                  f"  Reason : {outcome.error}\n"
                  f"  The results above are still valid; nothing was stored in the database.")
            if outcome.recovery_path:
                print(f"  Recovery copy: {outcome.recovery_path}\n"
                      f"  Import it later with: python scripts/results.py import {outcome.recovery_path}")
    if len(suites) > 1:
        print("\n=== COMPARISON ===\n" + compare(suites))
    if not all_stored:
        sys.exit(1)

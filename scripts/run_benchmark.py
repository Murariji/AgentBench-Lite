"""Run the whole shop benchmark suite and print a report.

    python scripts/run_benchmark.py --agent careful          # scripted agent, expected 10/10 (free)
    python scripts/run_benchmark.py --agent sloppy           # scripted agent with 4 trap mistakes (free)
    python scripts/run_benchmark.py --compare                # careful vs sloppy, side by side (free)
    python scripts/run_benchmark.py --agent sloppy --save    # also export JSON to results/
    python scripts/run_benchmark.py --agent gemini           # REAL Gemini: prints the estimate, sends NOTHING
    python scripts/run_benchmark.py --agent gemini --yes     # REAL Gemini: actually runs (free tier)

Real runs: >= 6 s between requests, a hard request budget (--budget, default 80) and a
circuit breaker that stops the suite on auth / quota errors.

Every finished suite is stored automatically in data/results.db (see scripts/results.py).
If that save fails, the result is NOT lost: a JSON recovery copy is written to results/.
"""

import argparse
import hashlib
import sys

from agentbench.benchmark import estimate_requests, run_suite
from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.models import AgentConfig
from agentbench.report import compare, export_json, format_report
from agentbench.runner import DEFAULT_SYSTEM_PROMPT
from agentbench.storage import DEFAULT_RESULTS_DB, save_with_recovery
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

GEMINI_PACING_SECONDS = 6.0  # <= 10 requests per minute
DEFAULT_BUDGET = 80


def gemini_client():
    """Created only AFTER --yes. Building the client sends no request."""
    from dotenv import find_dotenv, load_dotenv

    from agentbench.llm.gemini import GeminiClient

    load_dotenv(find_dotenv(usecwd=True))
    return GeminiClient()


def gemini_config(model: str = "see .env / default") -> AgentConfig:
    return AgentConfig(name="gemini-default", provider="gemini", model=model,
                       system_prompt=DEFAULT_SYSTEM_PROMPT, max_attempts=3,
                       min_interval_seconds=GEMINI_PACING_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=["careful", "sloppy", "gemini"], default="careful")
    parser.add_argument("--compare", action="store_true", help="run careful and sloppy, compare them")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--save", action="store_true", help="export JSON results to results/")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="hard cap on real requests")
    parser.add_argument("--yes", action="store_true", help="confirm a REAL (quota-using) run")
    parser.add_argument("--results-db", default=str(DEFAULT_RESULTS_DB), help="where runs are stored")
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.budget < 1:
        parser.error("--budget must be at least 1")
    real = args.agent == "gemini" and not args.compare

    if real:
        # The estimate comes FIRST; without --yes we stop here with zero API calls.
        estimate = estimate_requests(SHOP_TASKS, gemini_config(), repeats=args.repeats, budget=args.budget)
        print("=== REAL Gemini run (uses free-tier quota) ===")
        print(estimate.describe())
        print(f"Pacing     : at least {GEMINI_PACING_SECONDS:.0f} s between requests")
        if not args.yes:
            print("\nNothing was sent. Add --yes to start this run.")
            raise SystemExit(0)

    if not DEFAULT_DB_PATH.exists():
        build_shop_db(DEFAULT_DB_PATH)  # only builds when missing; never overwrites
    dataset = f"{DEFAULT_DB_PATH.name} sha256:{hashlib.sha256(DEFAULT_DB_PATH.read_bytes()).hexdigest()[:12]}"

    with ReadOnlySQLite(DEFAULT_DB_PATH) as db:
        tools = shop_registry(db)
        if real:
            client = gemini_client()
            print(f"\n=== running shop suite with REAL {client.name} ===")
            suites = [run_suite(SHOP_TASKS, gemini_config(client.model), lambda task, repeat: client, tools,
                                suite_name="shop", repeats=args.repeats, dataset=dataset,
                                request_budget=args.budget)]
        else:
            suites = []
            for kind in (["careful", "sloppy"] if args.compare else [args.agent]):
                print(f"\n=== running shop suite with the {kind} SCRIPTED agent ===")
                suites.append(run_suite(SHOP_TASKS, scripted_config(kind), scripted_agent(kind), tools,
                                        suite_name="shop", repeats=args.repeats, dataset=dataset))

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

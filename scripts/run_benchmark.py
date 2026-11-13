"""Run the whole shop benchmark suite and print a report (offline, free).

    python scripts/run_benchmark.py --agent careful          # scripted agent, expected 10/10
    python scripts/run_benchmark.py --agent sloppy           # scripted agent with 4 trap mistakes
    python scripts/run_benchmark.py --compare                # careful vs sloppy, side by side
    python scripts/run_benchmark.py --agent sloppy --save    # also export JSON to results/
    python scripts/run_benchmark.py --agent careful --repeats 2

Real Gemini suite runs are added in Step 6.3 (with pacing, a request budget and --yes).
"""

import argparse
import hashlib

from agentbench.benchmark import run_suite
from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.report import compare, export_json, format_report
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite


def run(kind: str, repeats: int, db: ReadOnlySQLite, dataset: str):
    print(f"\n=== running shop suite with the {kind} SCRIPTED agent ===")
    return run_suite(SHOP_TASKS, scripted_config(kind), scripted_agent(kind), shop_registry(db),
                     suite_name="shop", repeats=repeats, dataset=dataset)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=["careful", "sloppy", "gemini"], default="careful")
    parser.add_argument("--compare", action="store_true", help="run careful and sloppy, compare them")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--save", action="store_true", help="export JSON results to results/")
    args = parser.parse_args()

    if args.agent == "gemini" and not args.compare:
        parser.exit(1, "Real Gemini suite runs arrive in Step 6.3 (pacing, budget, --yes). "
                       "For one real task now: python scripts/run_shop_task.py --gemini shop-004\n")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    if not DEFAULT_DB_PATH.exists():
        build_shop_db(DEFAULT_DB_PATH)  # only builds when missing; never overwrites
    dataset = f"{DEFAULT_DB_PATH.name} sha256:{hashlib.sha256(DEFAULT_DB_PATH.read_bytes()).hexdigest()[:12]}"

    with ReadOnlySQLite(DEFAULT_DB_PATH) as db:
        kinds = ["careful", "sloppy"] if args.compare else [args.agent]
        suites = [run(kind, args.repeats, db, dataset) for kind in kinds]

    for suite in suites:
        print("\n" + format_report(suite))
        if args.save:
            print(f"\nSaved: {export_json(suite)}")
    if len(suites) > 1:
        print("\n=== COMPARISON ===\n" + compare(suites))

"""Pre-register a benchmark suite: freeze its tasks, answers, grading and tools BEFORE real runs.

    python scripts/register_suite.py shop-hard            # writes src/agentbench/suites/registrations/shop-hard.v1.json
    python scripts/register_suite.py shop-hard --version 2

Never overwrites an existing registration (a change = a new version). No API calls.
"""

import argparse
import hashlib
from pathlib import Path

from agentbench.datasets import DEFAULT_DB_PATH
from agentbench.registration import build_registration, git_state, write_registration
from agentbench.suites import SUITES, shop_registry
from agentbench.tools import ReadOnlySQLite

ROOT = Path(__file__).resolve().parents[1]
SUITE_SOURCES = {"shop": "src/agentbench/suites/shop.py", "shop-hard": "src/agentbench/suites/shop_hard.py"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", choices=sorted(SUITES))
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()

    if not DEFAULT_DB_PATH.exists():
        raise SystemExit(f"{DEFAULT_DB_PATH} is missing; build it first: python scripts/build_shop_db.py")
    dataset = f"{DEFAULT_DB_PATH.name} sha256:{hashlib.sha256(DEFAULT_DB_PATH.read_bytes()).hexdigest()[:12]}"
    with ReadOnlySQLite(DEFAULT_DB_PATH) as db:
        tools = shop_registry(db).specs()
    head, committed = git_state(ROOT, ROOT / SUITE_SOURCES[args.suite])
    record = build_registration(args.suite, args.version, SUITES[args.suite], tools, dataset=dataset,
                                git_head=head, source_committed=committed)
    try:
        path = write_registration(record)
    except FileExistsError:
        raise SystemExit(f"{args.suite} v{args.version} is already registered; a change needs a new --version")
    print(f"Registered {args.suite} v{args.version}: suite {record['suite_fingerprint']}, "
          f"tasks {record['tasks_fingerprint']}, tools {record['tools_fingerprint']}, git {head}")
    if committed is False:
        print("Note: the suite file has uncommitted changes; commit it together with this registration.")
    print(f"Written: {path.relative_to(ROOT)}")

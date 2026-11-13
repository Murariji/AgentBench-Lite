"""Compare the API with its pinned contract - and update the contract only DELIBERATELY.

    python scripts/update_api_contract.py                                   # show differences (changes nothing)
    python scripts/update_api_contract.py --write --reason "add field X for the dashboard"

--write requires --reason. The reason and the list of differences are appended to docs/api.md
("Contract changes"), so every intentional change is visible in git history. No API calls.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from agentbench.api import create_app
from agentbench.api.contract import CONTRACT_FILE, build_contract, contract_diff, load_contract

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="write the current contract (needs --reason)")
    parser.add_argument("--reason", help="why the contract changes (recorded in docs/api.md)")
    parser.add_argument("--contract-file", default=str(CONTRACT_FILE))
    parser.add_argument("--changelog", default=str(ROOT / "docs" / "api.md"))
    args = parser.parse_args()

    current = build_contract(create_app(":memory:").openapi())
    path = Path(args.contract_file)
    old = load_contract(path) if path.exists() else {"endpoints": {}, "schemas": {}}
    changes = contract_diff(old, current)
    print("\n".join(changes) if changes else "The API matches its pinned contract.")
    if not args.write:
        raise SystemExit(1 if changes else 0)
    if not args.reason or not args.reason.strip():
        parser.error("--write needs --reason: say WHY the contract changes")
    if not changes:
        raise SystemExit("Nothing to write: the contract is unchanged.")
    path.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log = Path(args.changelog)
    entry = (f"\n### {datetime.now(timezone.utc):%Y-%m-%d} — {args.reason.strip()}\n\n"
             + "\n".join(f"- {c}" for c in changes) + "\n")
    log.write_text((log.read_text(encoding="utf-8") if log.exists() else "") + entry, encoding="utf-8")
    print(f"\nWritten {path} ({len(changes)} change(s)); reason recorded in {log}")

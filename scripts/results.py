"""Browse stored benchmark runs in data/results.db (free, offline, no API calls).

    python scripts/results.py list                      # all runs, newest first
    python scripts/results.py list --real               # only real LLM runs (no scripted agents)
    python scripts/results.py show <id>                 # full report of one run
    python scripts/results.py compare <id1> <id2>       # side by side, with the fairness check
    python scripts/results.py history <task_id>         # one task across every run, e.g. shop-010
    python scripts/results.py import results/<file>.json [more files...]

<id> can be the first few characters of a suite id (like a short git commit id).
"""

import argparse
import sys

from agentbench.report import compare, format_report, load_json
from agentbench.storage import (DEFAULT_RESULTS_DB, DuplicateSuiteError, ResultStore, StorageError)


def cmd_list(store: ResultStore, args) -> None:
    rows = store.list_suites(real_only=args.real, limit=args.limit)
    if not rows:
        print("No stored runs yet. Run: python scripts/run_benchmark.py")
        return
    print(f"{'ID':8}  {'STARTED (UTC)':16}  {'KIND':8}  {'CONFIG':16}  {'MODEL':22}  "
          f"{'RUNS':>7}  {'PASS RATE':16}  {'REQ':>4}  STATUS")
    for s in rows:
        runs = f"{s.scheduled_runs // s.repeats}x{s.repeats}"
        status = "complete" if s.complete else f"INCOMPLETE ({s.infra_errors} infra, {s.skipped} skipped)"
        print(f"{s.suite_id[:8]:8}  {s.started_at:%Y-%m-%d %H:%M}  {'SCRIPTED' if s.is_scripted else 'REAL':8}  "
              f"{s.config_name[:16]:16}  {s.model[:22]:22}  {runs:>7}  {str(s.pass_rate):16}  "
              f"{s.total_llm_calls:>4}  {status}")


def cmd_show(store: ResultStore, args) -> None:
    print(format_report(store.load(store.resolve(args.id))))


def cmd_compare(store: ResultStore, args) -> None:
    print(compare([store.load(store.resolve(i)) for i in args.ids]))


def cmd_history(store: ResultStore, args) -> None:
    rows = store.task_history(args.task_id)
    if not rows:
        print(f"No stored runs of {args.task_id!r}.")
        return
    print(f"History of {args.task_id} (newest first), {len(rows)} scheduled run(s)")
    print(f"{'SUITE':8}  {'STARTED (UTC)':16}  {'CONFIG':16}  {'MODEL':22}  {'TASK VER':8}  "
          f"{'REP':>3}  {'OUTCOME':11}  {'CALLS':>5}  ANSWER / REASON")
    for h in rows:
        detail = h.reason if h.outcome == "skipped" else (
            f"({h.error_kind})" if h.outcome == "infra_error" else repr(h.final_answer))
        calls = "-" if h.llm_calls is None else str(h.llm_calls)
        print(f"{h.suite_id[:8]:8}  {h.started_at:%Y-%m-%d %H:%M}  {h.config_name[:16]:16}  {h.model[:22]:22}  "
              f"{(h.task_hash or '-')[:8]:8}  {h.repeat + 1:>3}  {h.outcome.upper():11}  {calls:>5}  {detail}")


def cmd_import(store: ResultStore, args) -> None:
    for path in args.files:
        suite = load_json(path)  # validated again on load; stored metrics are ignored
        try:
            store.save(suite)
            print(f"imported      {suite.suite_id[:8]}  <- {path}")
        except DuplicateSuiteError:
            print(f"already stored {suite.suite_id[:8]}  <- {path} (nothing changed)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DEFAULT_RESULTS_DB), help="results database file")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="all stored runs, newest first")
    p.add_argument("--real", action="store_true", help="only real LLM runs")
    p.add_argument("--limit", type=int)
    p.set_defaults(handler=cmd_list)
    p = sub.add_parser("show", help="full report of one run")
    p.add_argument("id")
    p.set_defaults(handler=cmd_show)
    p = sub.add_parser("compare", help="compare two or more runs")
    p.add_argument("ids", nargs="+")
    p.set_defaults(handler=cmd_compare)
    p = sub.add_parser("history", help="one task across every run")
    p.add_argument("task_id")
    p.set_defaults(handler=cmd_history)
    p = sub.add_parser("import", help="store exported JSON files")
    p.add_argument("files", nargs="+")
    p.set_defaults(handler=cmd_import)
    args = parser.parse_args()

    if args.command == "compare" and len(args.ids) < 2:
        parser.error("compare needs at least two ids")
    try:
        with ResultStore(args.db) as store:
            args.handler(store, args)
    except (StorageError, ValueError, OSError) as exc:  # a clear message, not a traceback
        sys.exit(f"error: {exc}")

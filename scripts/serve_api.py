"""Start the AgentBench-Lite API on THIS computer only (127.0.0.1).

    python scripts/serve_api.py                     # http://127.0.0.1:8000/docs  (interactive docs page)
    python scripts/serve_api.py --port 8001 --db data/results.db
    python scripts/serve_api.py --allow-real-runs --max-real-budget 100    # permit REAL Gemini runs (quota!)

Real Gemini runs are OFF by default. Even with --allow-real-runs, each run also needs confirm=true, a
budget within --max-real-budget, and a passing registration guard. Scripted runs are always allowed.

The address is fixed to 127.0.0.1 on purpose: nothing on your network can reach it, and there is no login.
Stop it with Ctrl+C. Finished results stay safe in SQLite; the in-memory job list is cleared.
"""

import argparse

HOST = "127.0.0.1"   # local only - deliberately NOT configurable

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=None, help="results database (default: data/results.db)")
    parser.add_argument("--allow-real-runs", action="store_true",
                        help="permit REAL Gemini runs (each still needs confirm + budget + registration guard)")
    parser.add_argument("--max-real-budget", type=int, default=100,
                        help="the largest request budget a real run may ask for (default 100)")
    args = parser.parse_args()
    if args.max_real_budget < 1:
        parser.error("--max-real-budget must be at least 1")

    try:
        import uvicorn

        from agentbench.api import create_app
    except ImportError:
        raise SystemExit('The API needs the "api" extra: python -m pip install -e ".[dev,api]"')
    from agentbench.storage import DEFAULT_RESULTS_DB

    print(f"AgentBench-Lite API on http://{HOST}:{args.port}  (docs: http://{HOST}:{args.port}/docs)")
    if args.allow_real_runs:
        print(f"REAL Gemini runs ENABLED (max budget {args.max_real_budget} requests per run). "
              "Each run still needs confirm=true and a passing registration guard.")
    else:
        print("Real Gemini runs are disabled (scripted runs only). Use --allow-real-runs to enable.")
    uvicorn.run(create_app(args.db or DEFAULT_RESULTS_DB, allow_real_runs=args.allow_real_runs,
                           max_real_budget=args.max_real_budget), host=HOST, port=args.port)

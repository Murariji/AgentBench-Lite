"""Start the AgentBench-Lite API on THIS computer only (127.0.0.1). Read-only in Phase 9.1.

    python scripts/serve_api.py                 # http://127.0.0.1:8000/docs  (interactive docs page)
    python scripts/serve_api.py --port 8001 --db data/results.db

The address is fixed to 127.0.0.1 on purpose: nothing on your network can reach it, and there is
no login. Stop it with Ctrl+C - completed results stay safe in the SQLite file.
"""

import argparse

HOST = "127.0.0.1"   # local only - deliberately NOT configurable

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=None, help="results database (default: data/results.db)")
    args = parser.parse_args()

    try:
        import uvicorn

        from agentbench.api import create_app
    except ImportError:
        raise SystemExit('The API needs the "api" extra: python -m pip install -e ".[dev,api]"')
    from agentbench.storage import DEFAULT_RESULTS_DB

    print(f"AgentBench-Lite API on http://{HOST}:{args.port}  (docs: http://{HOST}:{args.port}/docs)")
    uvicorn.run(create_app(args.db or DEFAULT_RESULTS_DB), host=HOST, port=args.port)

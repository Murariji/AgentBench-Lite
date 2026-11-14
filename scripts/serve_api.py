"""Start the AgentBench-Lite API on THIS computer only (127.0.0.1).

    python scripts/serve_api.py                     # http://127.0.0.1:8000/docs  (interactive docs page)
    python scripts/serve_api.py --port 8001 --db data/results.db
    python scripts/serve_api.py --cors-origin http://localhost:3000      # allow one more browser origin
    python scripts/serve_api.py --allow-real-runs --max-real-budget 100  # permit REAL Gemini runs (quota!)
    python scripts/serve_api.py --container          # ONLY inside Docker (the Dockerfile does this for you)

Browsers: only http://localhost:5173 and http://127.0.0.1:5173 (the React dev server) may read responses,
plus any --cors-origin you add. Never '*'. CORS is a browser rule, NOT the safety layer: the real-run
gates are checked on the server for every client.

Real Gemini runs are OFF by default. Even with --allow-real-runs, each run also needs confirm=true, a
budget within --max-real-budget, and a passing registration guard. Scripted runs are always allowed.

The address is fixed to 127.0.0.1 on purpose: nothing on your network can reach it, and there is no login.
The one exception is --container (Phase 11.1): inside a Docker container the server must listen on 0.0.0.0,
or Docker cannot forward the port to it. It refuses to start outside a container, and the image is meant to
be published on this computer only: docker run -p 127.0.0.1:8000:8000 ...
Stop it with Ctrl+C. Finished results stay safe in SQLite; the in-memory job list is cleared.
"""

import argparse

HOST = "127.0.0.1"   # local only - deliberately NOT configurable (--container is the single, checked exception)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=None, help="results database (default: data/results.db)")
    parser.add_argument("--allow-real-runs", action="store_true",
                        help="permit REAL Gemini runs (each still needs confirm + budget + registration guard)")
    parser.add_argument("--max-real-budget", type=int, default=100,
                        help="the largest request budget a real run may ask for (default 100)")
    parser.add_argument("--cors-origin", action="append", default=[], metavar="ORIGIN",
                        help="an extra exact browser origin allowed to read responses (repeatable)")
    parser.add_argument("--container", action="store_true",
                        help="listen on 0.0.0.0 INSIDE a Docker container (refused anywhere else)")
    args = parser.parse_args()
    if args.max_real_budget < 1:
        parser.error("--max-real-budget must be at least 1")

    try:
        import uvicorn

        from agentbench.api import create_app
        from agentbench.api.app import DEFAULT_CORS_ORIGINS, check_startup, listen_host, validate_origins
    except ImportError:
        raise SystemExit('The API needs the "api" extra: python -m pip install -e ".[dev,api]"')
    from agentbench.storage import DEFAULT_RESULTS_DB

    try:
        host = listen_host(args.container)   # HOST unless --container inside a real container
    except ValueError as exc:
        parser.error(str(exc))
    db = args.db or DEFAULT_RESULTS_DB
    try:
        origins = validate_origins([*DEFAULT_CORS_ORIGINS, *args.cors_origin])
    except ValueError as exc:
        parser.error(str(exc))
    problem = check_startup(db)          # BEFORE starting: a server that fails every request helps no one
    if problem:
        raise SystemExit(f"Not starting: {problem}")

    if host == HOST:
        print(f"AgentBench-Lite API on http://{HOST}:{args.port}  (docs: http://{HOST}:{args.port}/docs)")
    else:
        print(f"AgentBench-Lite API in a container, listening on {host}:{args.port} inside it. On your computer "
              f"use the port you published, e.g. http://127.0.0.1:{args.port}/docs with -p 127.0.0.1:{args.port}:{args.port}")
    print(f"Browser origins allowed: {', '.join(origins)}")
    if args.allow_real_runs:
        print(f"REAL Gemini runs ENABLED (max budget {args.max_real_budget} requests per run). "
              "Each run still needs confirm=true and a passing registration guard.")
    else:
        print("Real Gemini runs are disabled (scripted runs only). Use --allow-real-runs to enable.")
    uvicorn.run(create_app(db, allow_real_runs=args.allow_real_runs, max_real_budget=args.max_real_budget,
                           cors_origins=origins), host=host, port=args.port)

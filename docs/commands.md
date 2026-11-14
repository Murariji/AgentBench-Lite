# Command reference

Windows PowerShell, from the repo root (`AgentBench-Lite`) unless a line says `cd dashboard`.
Activate the virtual environment first for every `python` command: `.\.venv\Scripts\Activate.ps1`.

## 1. Run locally (no Docker)

**Once:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,api,gemini]"
cd dashboard; npm install; cd ..
Copy-Item .env.example .env      # then add your free Gemini key (only for real runs)
```

**Every time, two terminals:**

| Terminal | What | Command |
|---|---|---|
| 1 | API | `python scripts/serve_api.py` → http://127.0.0.1:8000/docs |
| 1 (instead) | API with real Gemini runs | `python scripts/serve_api.py --allow-real-runs` |
| 2 | Dashboard | `cd dashboard` then `npm run dev` → http://localhost:5173 |

Stop either with Ctrl+C.

## 2. Docker (no Python or Node needed)

```powershell
git clone https://github.com/Murariji/AgentBench-Lite.git
cd AgentBench-Lite
docker compose up --build                     # API + dashboard, scripted runs only → http://localhost:5173
```

| Task | Command |
|---|---|
| With real Gemini runs (needs `.env`) | `docker compose -f docker-compose.yml -f docker-compose.real.yml up --build` |
| In the background / status / logs | `docker compose up -d` / `docker compose ps` / `docker compose logs -f api` |
| Stop and remove containers (data stays) | `docker compose down` |
| API image only | `docker build -t agentbench-api .` then `docker run --rm -p 127.0.0.1:8000:8000 -v "${PWD}/data:/app/data" -v "${PWD}/results:/app/results" agentbench-api` |
| Prove the API image works (30 checks, free) | `python scripts/docker_check_api.py` |
| Free disk space | `docker system prune` |

Docker and the local setup use the same ports (8000, 5173): run one or the other. Details: [docker.md](docker.md).

## 3. Benchmarks

```powershell
python scripts/run_benchmark.py --agent careful                       # scripted, free
python scripts/run_benchmark.py --suite shop-hard --compare           # careful vs sloppy, free
python scripts/run_benchmark.py --agent gemini --suite shop-hard --budget 100              # estimate only, sends nothing
python scripts/run_benchmark.py --agent gemini --suite shop-hard --budget 100 --yes --save # REAL run (quota)
```

## 4. Stored results (free, offline)

```powershell
python scripts/results.py list                  # all runs, newest first   (--real: real runs only)
python scripts/results.py show d8e976c8         # one run in full
python scripts/results.py compare e601af16 b36e1e4a d8e976c8
python scripts/results.py history hard-001      # one task across every run
python scripts/results.py failures --all        # failure categories across all runs
```

## 5. Tests and builds

```powershell
pytest                                          # Python tests
cd dashboard; npm run check; cd ..              # types up to date + type check + dashboard tests
cd dashboard; npm run build; cd ..              # production build
```

## 6. Maintenance (rarely)

```powershell
python scripts/build_shop_db.py                 # build data/shop.db if missing (never overwrites)
python scripts/register_suite.py shop-hard --version 2    # only after changing the suite's tasks
python scripts/export_openapi.py                # refresh dashboard/openapi.json after an API change
cd dashboard; npm run gen:types; cd ..          # then regenerate the dashboard's types
```

Careful: `export_openapi.py` has no `--help`. It always runs and rewrites the file.

## 7. Git

```powershell
git status
git add .
git commit -m "message"
git push
```

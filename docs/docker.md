# Running AgentBench-Lite in Docker (Phase 11)

Two images, started together by `docker compose`:

| Image | What is inside | Size | Port on your computer |
|---|---|---|---|
| `agentbench-api` | Python 3.12, the framework, FastAPI, Uvicorn, the Gemini SDK | ~264 MB | `127.0.0.1:8000` |
| `agentbench-dashboard` | the built React app, served by nginx (no Node, no source code) | ~75 MB | `127.0.0.1:5173` |

You need only **Docker Desktop** (and Git to clone): no Python, Node or virtual environment.
All commands are for **Windows PowerShell**, run from the repo root. They work the same in a macOS/Linux shell.

## Quick start (API + dashboard)

```powershell
git clone https://github.com/Murariji/AgentBench-Lite.git
cd AgentBench-Lite
docker compose up --build
```

Open **http://localhost:5173** (dashboard) and http://127.0.0.1:8000/docs (API docs).
Stop with Ctrl+C, then `docker compose down` to remove the containers. Your `data/` folder stays.

The first build downloads packages and takes a few minutes. Later starts reuse the cache and take seconds.

## Real Gemini runs (uses your free quota)

Real runs are **off** in the default setup: it never reads `.env` and never passes `--allow-real-runs`.
To turn them on, add the opt-in file:

```powershell
Copy-Item .env.example .env      # once; put your free AI Studio key in .env (never commit it)
docker compose -f docker-compose.yml -f docker-compose.real.yml up --build
```

The dashboard's API connection page then says "enabled". Each real run still needs the confirmation, a
budget of at most 100 requests, and a passing registration guard, exactly as without Docker.

## Everyday commands

| Task | Command |
|---|---|
| Start (scripted runs only) | `docker compose up --build` |
| Start in the background | `docker compose up -d` |
| Status and health | `docker compose ps` |
| Follow the logs | `docker compose logs -f api` (or `dashboard`) |
| Stop and remove the containers (data stays) | `docker compose down` |
| Rebuild after changing the code | `docker compose up --build` |
| Free disk space from old images and cache | `docker system prune` (asks first) |

**Ports already in use?** Compose needs 8000 and 5173. Stop `python scripts/serve_api.py` and `npm run dev`
first. Docker and the local setup are either-or.

## The safety rules, and where they live

| Rule | How |
|---|---|
| Only this computer can connect | every port is published as `127.0.0.1:...`. Never change it to `8000:8000`: there is no login. |
| No API key in any image | `.dockerignore` (allow-list) keeps `.env` out of the build. The key arrives only at start, via `docker-compose.real.yml` / `--env-file`. |
| Real runs off by default | the image starts `serve_api.py` without `--allow-real-runs`; only the opt-in file adds it. |
| Server never runs as root | `scripts/docker-entrypoint.sh` picks a normal user (see below) and hands over with `setpriv`. |
| Results survive the containers | `./data` and `./results` are shared folders (bind mounts) on your disk. |
| The browser may only talk to the API from the dashboard | CORS: the API accepts `http://localhost:5173` / `http://127.0.0.1:5173` only. That is why the dashboard keeps port 5173. |

## How the pieces fit

```
your browser ──► http://localhost:5173  ─► dashboard container (nginx, port 8080 inside)  : only files
      │
      └────────► http://127.0.0.1:8000  ─► api container (Uvicorn on 0.0.0.0:8000 inside) : the API
                                               │
                                               └─ /app/data  ◄──shared──►  ./data on your disk
```

The dashboard container never talks to the API. Your **browser** loads the page from nginx, then calls the
API directly. That is why the API address baked into the dashboard is `http://127.0.0.1:8000`, an address
your browser can reach.

## Why `--container` exists

Normally the server listens on `127.0.0.1`, so only this computer can reach it. Inside a container,
`127.0.0.1` is the **container's own** loopback: Docker's port forwarding arrives on the container's network
interface, not on its loopback, so nothing could connect. The server therefore listens on `0.0.0.0` (every
interface) **inside the container**, and the protection moves to the port mapping on your computer
(`127.0.0.1:...`).

`--container` refuses to start unless the files Docker or Podman create in every container (`/.dockerenv`,
`/run/.containerenv`) are present. Running `python scripts/serve_api.py` on your computer therefore stays
local-only, even if someone adds `--container` by mistake.

## Which user the API runs as

A shared folder keeps its owner's numeric user id. On Linux your user is usually 1000. A server running as
the image's user (10001) could not write `results.db` there. `scripts/docker-entrypoint.sh` runs as root for a
moment, only to decide:

| Your `data/` folder | The server runs as |
|---|---|
| owned by a normal user (Linux) | **that user**, so new files belong to you |
| owned by root (Docker Desktop on Windows/macOS shows shared folders this way) | `agentbench` (10001) |
| owned by root, not writable, **empty** (Docker just created it) | `agentbench`, after taking over that empty folder |
| owned by root, not writable, **already holds files** | does not start, with a clear message; your files are untouched |

`.gitattributes` keeps this script in Unix line endings: a Windows checkout would otherwise break `sh`.

## API image only (without compose)

```powershell
docker build -t agentbench-api .
docker run --rm -p 127.0.0.1:8000:8000 -v "${PWD}/data:/app/data" -v "${PWD}/results:/app/results" agentbench-api
# real runs: add  --env-file .env  before the image name and  --allow-real-runs  after it
```

Everything after the image name is passed to `scripts/serve_api.py` (`--allow-real-runs`,
`--max-real-budget 50`, ...).

## Check that it works

```powershell
python scripts/docker_check_api.py      # needs the project's .venv
```

This builds the API image and runs 30 checks: the build context, the image contents, the `--container`
refusal, health, the server not running as root, endpoints, a scripted run, secrets, persistence and
networking. It works on a temporary copy of your `shop.db`, never on your real `data/` folder, and it never
sends anything to Gemini.

## Known limitations

- **A fresh clone starts empty.** Stored runs live in `data/results.db`, which is not in Git. Scripted runs
  from the "Start a run" page fill it for free.
- **Mount your `data/` folder for real runs.** The registration guard checks the `shop.db` fingerprint, a hash
  of the file's **bytes**. SQLite writes its own version number into the file header. A `shop.db` built
  inside the container (SQLite 3.46.1) has exactly the same data as one built on Windows (SQLite 3.45.3): both
  `iterdump()` hashes are `1031b73af95c`. But the bytes differ, so the guard reports `differs` and refuses real
  runs. That is the guard working as designed. A content-based fingerprint would fix this, but it would change
  the fingerprint of every stored run, so it is left as a future decision. A visitor building their own
  `shop.db` may hit the same refusal.
- **No login.** For this computer only. Never publish the ports on your network or on a server.
- **One run at a time, job list in memory.** Restarting the API clears the job list. Finished runs are in SQLite
  and stay.
- **No Content-Security-Policy header** on the dashboard yet. The page's small inline theme script would need a
  hash in the policy. It is not needed for a local-only app.
- **Image versions follow patch releases** (`python:3.12-slim`, `node:20-alpine`, `nginx-unprivileged:1.27-alpine`),
  so a rebuild later may use slightly newer patches.

# Phase 11 notes — Docker

## Step 11.1: the API image

### The concepts
| Concept | In plain words |
|---|---|
| image | a frozen, ready-to-run box: an operating system layer + Python + our code. Built once, started many times. Like a recipe that is already cooked and packed. |
| container | one running copy of an image. Delete it and start a new one: same starting point every time. |
| Dockerfile | the build instructions for an image, one step per line (`FROM`, `COPY`, `RUN` ...). |
| layer | every step's result is cached. Change a late step and Docker reuses all the earlier ones, so the order of steps matters for speed. |
| build context | the folder Docker sends to the builder. `.dockerignore` decides what may NOT be sent. |
| volume / bind mount (`-v`) | a folder on YOUR disk shown inside the container. Data written there survives the container. |
| port publishing (`-p host:container`) | forwards a port on your computer to a port inside the container. `127.0.0.1:8000:8000` = only this computer. |
| ENTRYPOINT / CMD | the fixed command / the default extra options that you may replace at `docker run`. |
| HEALTHCHECK | a command Docker runs regularly; `docker ps` then shows healthy/unhealthy. |

### Decisions and trade-offs
1. **Allow-list `.dockerignore`.** It starts with `*` (ignore everything) and lets back in only `src/`,
   `scripts/`, `pyproject.toml`, `README.md` and `LICENSE`. With a block-list, every new secret or big folder
   would leak in until someone remembered to add it. The trade-off is that a new folder the image really
   needs must be allowed explicitly, and the build fails loudly if it is missing (safe direction).
2. **`--container` instead of a `--host` option.** A `--host` option would let anyone type `0.0.0.0` on their own
   computer. `--container` can only mean "inside Docker", and it checks this (`/.dockerenv`). The old rule
   "the address is fixed to 127.0.0.1" stays true everywhere else, and the existing tests that forbid `--host`
   still pass.
3. **Protection moves to `-p 127.0.0.1:...`.** Inside the container the server must listen on `0.0.0.0`.
   Step 8 of `docker_check_api.py` proves why: without `--container`, the server runs but cannot be reached
   from outside.
4. **Normal install, not editable.** The image copies the code into site-packages, then deletes `src/`. That
   exposed a hidden bug: the two JSON files (API contract, suite registrations) were only found because the
   editable install reads straight from `src/`. `[tool.setuptools.package-data]` now lists them, and a test
   fails if a new data file is ever added without being listed.
5. **Non-root user (`agentbench`, uid 10001).** If something ever went wrong inside the server, it could
   not change the container's system files. It may write only to `/app/data` and `/app/results`.
6. **One image with the Gemini SDK included.** It is +~100 MB, but real runs work with the same image. A
   separate "real" image would be two things to build and keep in sync.
7. **Simple single-stage build.** All dependencies are ready-made wheels (nothing to compile), so a
   multi-stage build would save very little. `PIP_NO_CACHE_DIR` and deleting `src/` keep the image clean.
8. **The key at run time (`--env-file .env`).** It is never written in the Dockerfile and never copied into the
   image. One honest caveat: anyone who can run `docker inspect` on the RUNNING container can see its
   environment variables. That is normal for Docker, and fine on your own computer.

### What we found
- **The `shop.db` fingerprint depends on the SQLite version.** The same data gives different file bytes
  (Windows 3.45.3 vs container 3.46.1), because SQLite stores its version in the file header. The registration
  guard correctly refuses real runs on a container-built `shop.db`. The workaround is to mount `data/`. The
  long-term fix would be a content-based fingerprint (a decision for later, because it changes every
  stored fingerprint).

### How it was verified
- `scripts/docker_check_api.py`: 30 checks against a real container.
- `tests/test_docker_files.py`: 15 tests that run without Docker. Sabotage check: disabling the
  `--container` refusal broke 2 of them.
- Sabotage check on `.dockerignore`: removing the `*` line let `.git`, `.venv`, `data`, `tests` and `dashboard`
  into the build context. The check script lists the context and would flag them.

### Self-check questions
1. Why does a server listening on 127.0.0.1 inside a container not answer `docker run -p 8000:8000`?
2. What is the difference between `-p 8000:8000` and `-p 127.0.0.1:8000:8000`, and why does it matter for
   an API with no login?
3. Why is `.dockerignore` an allow-list here, and what happens if a new folder is needed in the image?
4. Where does `results.db` live when you use `-v "${PWD}/data:/app/data"`, and what happens to it after
   `docker rm`?
5. Why could a container-built `shop.db` make the registration guard refuse a real run, although the data is
   identical?
6. Why did the normal install in the image reveal a bug that the editable install had hidden?

## Step 11.2: dashboard image + docker compose

### The concepts
| Concept | In plain words |
|---|---|
| multi-stage build | one Dockerfile, two images: a big "kitchen" (Node) builds the app, only the finished dish (`dist/`) goes into the small "plate" (nginx). |
| nginx | a small, fast web server. Here it only hands out files. |
| SPA fallback | `/runs/abc` exists only inside React. On a refresh nginx has no such file, so it sends `index.html` (`try_files ... /index.html`). |
| docker compose | one file that starts several containers together, with their ports, folders and start order. |
| `depends_on: service_healthy` | start the dashboard only after the API's health check passes. |
| compose override file | a second file merged on top of the first (`-f a.yml -f b.yml`). Used for the opt-in real-runs setup. |
| entrypoint script | a small program that runs first when a container starts, before the real server. |
| uid | the number Linux uses for a user. Shared folders keep the owner's number, not the name. |

### Decisions and trade-offs
1. **The dashboard is built inside Docker** (`npm ci` + `npm run build`), not copied from your `dist/`. The image
   is then the same on every computer. It is slower the first time (about 4 minutes of downloads), then cached.
2. **The unprivileged nginx image** (runs as user 101, port 8080) instead of the standard one that starts as root.
3. **Port 5173 on the host** for the dashboard, because it is one of the two origins the API's CORS allows. No API
   change was needed.
4. **The API address is baked in at build time** (`VITE_API_BASE`, default `http://127.0.0.1:8000`). It must be
   an address the BROWSER can reach, not the container name `api`: the browser, not nginx, calls the API.
5. **Real runs in a separate file** (`docker-compose.real.yml`). The default setup never even reads `.env`.
6. **Entrypoint picks the user (fixed in part 3).** The first version always ran as 10001. On Linux that user
   could not write into a shared `data/` folder owned by your user (1000). Docker Desktop hid this because it
   shows shared folders as root-owned with full rights. The script now runs as the folder's owner, and never
   changes a folder that already holds files.
7. **`.gitattributes` forces LF for `*.sh`.** With `core.autocrlf=true`, Git would check the script out with Windows
   line endings, and `sh` inside Linux would fail.

### How it was verified
- Dashboard container: deep links 200 (index.html), a missing asset a real 404, JS served as JavaScript,
  security headers present, runs as `nginx`, image 75 MB, `(healthy)`.
- Compose on a temporary copy of the data: start order (dashboard waited for the API to be healthy), CORS accepts
  `http://localhost:5173` and rejects other origins, scripted run saved, real run 403, data kept across
  `down` + `up`.
- Linux ownership simulated with Docker volumes: user-1000 folder → runs as 1000 and files stay 1000's; empty
  root folder → taken over; root folder with files → refused, file untouched.
- Headless Edge on the full stack with a copy of the real results: Overview, Runs, run details, API connection
  and Start a run all show real data, with no errors.
- Python 743 passed; `docker_check_api.py` 30/30.

### Self-check questions
7. Why is the final dashboard image 75 MB when `node_modules` alone is much bigger?
8. Why does nginx need `try_files $uri $uri/ /index.html`, and why must `/assets/` NOT fall back to index.html?
9. Why is the API address in the dashboard `127.0.0.1:8000` and not `http://api:8000`?
10. What does `docker compose -f docker-compose.yml -f docker-compose.real.yml up` change, and what does it NOT change?
11. Why did the permission problem not show up on Windows, and what would a Linux user have seen?
12. Why does the entrypoint refuse a root-owned folder that already holds files, instead of taking it over?

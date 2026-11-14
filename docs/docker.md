# Running the API in Docker (Phase 11.1)

The API image packs Python 3.12, the framework, FastAPI and Uvicorn. You need only Docker Desktop: no
Python or virtual environment. The dashboard and `docker compose` come in Phase 11.2.

All commands are for **Windows PowerShell**, run from the repo root.

## Build

```powershell
docker build -t agentbench-api .
```

## Run (scripted runs only, the safe default)

```powershell
docker run --rm --name agentbench-api `
  -p 127.0.0.1:8000:8000 `
  -v "${PWD}/data:/app/data" `
  -v "${PWD}/results:/app/results" `
  agentbench-api
```

Open http://127.0.0.1:8000/docs. Stop it with Ctrl+C (or `docker stop agentbench-api`).

| Part | Why |
|---|---|
| `-p 127.0.0.1:8000:8000` | publishes the port on **this computer only**. `-p 8000:8000` would publish it on every network interface, so other devices on your network could reach an API that has no login. Always write `127.0.0.1:`. |
| `-v "${PWD}/data:/app/data"` | your `results.db` and `shop.db` stay on **your disk**. Without it they live inside the container and are lost when it is removed (`--rm`). |
| `-v "${PWD}/results:/app/results"` | recovery files of a run that could not be saved (rare) also land on your disk. |
| `--rm` | delete the container when it stops. Your data is safe in the mounted folders. |

## Real Gemini runs (uses your free quota)

The key is given **at run time**, from your `.env` file. It is never part of the image.

```powershell
docker run --rm --name agentbench-api `
  -p 127.0.0.1:8000:8000 `
  -v "${PWD}/data:/app/data" `
  -v "${PWD}/results:/app/results" `
  --env-file .env `
  agentbench-api --allow-real-runs
```

Everything after the image name is passed to `scripts/serve_api.py`, so `--allow-real-runs` and
`--max-real-budget 50` work exactly as before. Each real run still needs `confirm=true`, a budget within the
maximum, and a passing registration guard.

## Check that it works

```powershell
python scripts/docker_check_api.py
```

This builds the image, then runs 30 checks: the build context, the image contents, the `--container`
refusal, health, endpoints, a scripted run, secrets, persistence and networking. It works on a temporary copy
of your `shop.db`, never on your real `data/` folder, and it never sends anything to Gemini.

## Why `--container` exists

Normally the server listens on `127.0.0.1`, so only this computer can reach it. Inside a container,
`127.0.0.1` is the **container's own** loopback: Docker's port forwarding arrives on the container's network
interface, not on its loopback, so nothing could connect. The server therefore listens on `0.0.0.0` (every
interface) **inside the container**, and the protection moves to the port mapping on your computer
(`-p 127.0.0.1:...`).

`--container` refuses to start unless the files Docker or Podman create in every container (`/.dockerenv`,
`/run/.containerenv`) are present. Running `python scripts/serve_api.py` on your computer therefore stays
local-only, even if someone adds `--container` by mistake.

## Known limitations

- **Mount your `data/` folder.** The registration guard checks the `shop.db` fingerprint, a hash of the
  file's **bytes**. SQLite writes its own version number into the file header. A `shop.db` built inside the
  container (SQLite 3.46.1) has exactly the same data as one built on Windows (SQLite 3.45.3): both
  `iterdump()` hashes are `1031b73af95c`. But the bytes differ, so the guard reports `differs` and refuses real
  runs. That is the guard working as designed. Mounting your `data/` folder uses your original `shop.db`, so
  the fingerprints match. A content-based fingerprint would fix this, but it would change the
  fingerprint of every stored run, so it is left as a future decision.
- **No login.** The API is for this computer only. Never publish it with `-p 8000:8000` or on a server.
- **One run at a time, job list in memory.** Restarting the container clears the job list. Finished runs are in
  SQLite and stay.
- **Image size about 264 MB.** Most of it is the Python base image (about 120 MB) and Google's SDK with its
  cryptography libraries. The SDK is included so that real runs work without a second image.

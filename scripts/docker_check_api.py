"""Prove the API Docker image works (Phase 11.1). Free: SCRIPTED runs only, never a Gemini request.

    python scripts/docker_check_api.py            # build the image, then run every check
    python scripts/docker_check_api.py --no-build # reuse the existing agentbench-api image

What it checks, in order:
  1. build context  - what Docker would send into a build: no .env, databases, .venv, node_modules, .git
  2. image contents - runs as a normal user; no .env and no database baked into the image
  3. --container    - refused on this computer (outside Docker)
  4. start + health - the container starts and /health answers through 127.0.0.1 only
  5. endpoints      - read endpoints, estimates, real run refused (403), a scripted run stored
  6. secrets        - a fake "API key" given to the container never appears in any response or log
  7. persistence    - the stored run survives `docker restart` AND a brand-new container
  8. networking     - without --container the server is unreachable from outside the container

Your real data/ folder is never used: the checks run on a COPY in a temporary folder, deleted afterwards.
The fake key is random text, so even a mistaken Gemini call could only fail - it can never use your quota.
"""

import argparse
import json
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "agentbench-api"
FORBIDDEN_IN_CONTEXT = (".env", ".venv", "node_modules", ".git/", ".db", "dashboard/", "tests/", "data/")

failures: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}" + (f" - {detail}" if detail else ""))
    if not ok:
        failures.append(what)
    return ok


def docker(*args: str, check_rc: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    out = subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout)
    if check_rc and out.returncode != 0:
        raise SystemExit(f"docker {' '.join(args)} failed:\n{out.stderr or out.stdout}")
    return out


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def wait_healthy(port: int, seconds: int = 60) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            if call(port, "GET", "/health")[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


def start(name: str, port: int, workdir: Path, key: str, *extra: str) -> None:
    docker("run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:8000",
           "-e", f"GEMINI_API_KEY={key}",
           "-v", f"{workdir / 'data'}:/app/data", "-v", f"{workdir / 'results'}:/app/results", IMAGE, *extra)


def stored_runs(port: int) -> int:
    return json.loads(call(port, "GET", "/suites?limit=1")[1])["pagination"]["total"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-build", action="store_true", help="reuse the existing image instead of building")
    args = parser.parse_args()
    if shutil.which("docker") is None or docker("info", check_rc=False).returncode != 0:
        raise SystemExit("Docker is not available. Start Docker Desktop and try again.")

    tag = secrets.token_hex(4)
    names = [f"agentbench-check-{tag}-{i}" for i in range(4)]
    workdir = Path(tempfile.mkdtemp(prefix="agentbench-docker-check-"))
    key = "fake-key-" + secrets.token_hex(16)        # a canary: must never be shown anywhere
    seen: list[str] = []                              # every response body and log, searched for the canary
    try:
        print("1. Build context (.dockerignore)")
        listing = subprocess.run(
            ["docker", "build", "--no-cache", "--progress=plain", "-t", f"agentbench-context-{tag}", "-f", "-", str(ROOT)],
            input="FROM python:3.12-slim\nCOPY . /ctx\nRUN cd /ctx && find . -type f | sort\n",
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        files = sorted({line.split("./", 1)[1].strip() for line in listing.stderr.splitlines()
                        if " ./" in line and not line.rstrip().endswith("DONE")})
        docker("rmi", f"agentbench-context-{tag}", check_rc=False)
        check(listing.returncode == 0 and len(files) > 0, "build context could be listed", f"{len(files)} files")
        leaked = [f for f in files if any(bad in f"/{f}" or f.startswith(bad) or f.endswith(bad)
                                          for bad in FORBIDDEN_IN_CONTEXT)]
        check(not leaked, "no .env, database, .venv, node_modules, .git, tests, dashboard or data in the context",
              ", ".join(leaked[:5]))
        check(all(f.split("/")[0] in ("src", "scripts", "pyproject.toml", "README.md", "LICENSE") for f in files),
              "context holds only src/, scripts/, pyproject.toml, README.md, LICENSE")

        if not args.no_build:
            print("\n   Building the image (first build takes about a minute) ...")
            docker("build", "-t", IMAGE, str(ROOT))

        print("\n2. Image contents")
        user = docker("run", "--rm", "--entrypoint", "whoami", IMAGE).stdout.strip()
        check(user == "agentbench", "runs as a normal user, not root", user)
        found = docker("run", "--rm", "--entrypoint", "sh", IMAGE, "-c",
                       "find / \\( -name '.env' -o -name '.env.*' -o -name '*.db' \\) -not -path '/proc/*' "
                       "2>/dev/null; true").stdout.split()
        check(not found, "no .env file and no database inside the image", ", ".join(found[:5]))
        size = docker("image", "inspect", IMAGE, "--format", "{{.Size}}").stdout.strip()
        print(f"  [INFO] image size {int(size) / 1e6:.0f} MB")

        print("\n3. --container outside Docker")
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_api.py"), "--container"],
                             capture_output=True, text=True, timeout=60, cwd=ROOT)
        check(out.returncode != 0 and "only for running inside a Docker container" in out.stderr,
              "refused on this computer, with a clear message")

        # a COPY of your shop.db (so the registration check sees the same dataset as your real runs)
        (workdir / "data").mkdir()
        (workdir / "results").mkdir()
        if (ROOT / "data" / "shop.db").exists():     # read only; byte-identical, so the fingerprint matches
            shutil.copyfile(ROOT / "data" / "shop.db", workdir / "data" / "shop.db")

        print("\n4. Start + health")
        port = free_port()
        start(names[0], port, workdir, key)
        check(wait_healthy(port), "container started and /health answered", f"http://127.0.0.1:{port}")
        status, body = call(port, "GET", "/health")
        seen.append(body)
        health = json.loads(body)
        check(health.get("real_runs_enabled") is False, "real Gemini runs are OFF by default")
        published = docker("port", names[0], "8000").stdout.strip()
        check(published.startswith("127.0.0.1:"), "port published on 127.0.0.1 only", published)

        print("\n5. Endpoints")
        for path in ("/", "/registrations", "/suites", "/runs", "/openapi.json"):
            status, body = call(port, "GET", path)
            seen.append(body)
            check(status == 200, f"GET {path}", str(status))
        status, body = call(port, "POST", "/estimates", {"agent": "gemini", "suite": "shop-hard", "budget": 100,
                                                         "confirm": True})
        seen.append(body)
        estimate = json.loads(body)
        check(status == 200 and estimate["registration"]["status"] == "matches",
              "estimate: shop-hard registration matches inside the container", estimate["registration"]["line"])
        check(estimate["allowed"] is False, "estimate: real run not allowed (server started without the flag)")
        status, body = call(port, "POST", "/runs", {"agent": "gemini", "suite": "shop-hard", "tasks": ["hard-001"],
                                                    "budget": 10, "confirm": True})
        seen.append(body)
        check(status == 403, "real Gemini run refused with 403, nothing sent", str(status))
        before = stored_runs(port)
        status, body = call(port, "POST", "/runs", {"agent": "careful", "suite": "shop-hard",
                                                    "tasks": ["hard-001", "hard-007"]})
        seen.append(body)
        job = json.loads(body)
        check(status == 202, "scripted run accepted (202)", str(status))
        end = time.time() + 120
        while time.time() < end and job["status"] in ("queued", "running"):
            time.sleep(1)
            job = json.loads(call(port, "GET", f"/runs/{job['job_id']}")[1])
        seen.append(json.dumps(job))
        check(job["status"] == "finished" and job["saved"] is True, "scripted run finished and was saved",
              f"{job['status']}, suite {(job['suite_id'] or '')[:8]}")
        check(stored_runs(port) == before + 1, "stored run count went up by one", f"{before} -> {before + 1}")
        status, body = call(port, "GET", f"/suites/{job['suite_id']}")
        seen.append(body)
        check(status == 200, "the new run's details load", str(status))

        print("\n6. Secrets")
        seen.append(docker("logs", names[0]).stdout + docker("logs", names[0]).stderr)
        check(all(key not in text for text in seen), "the API key never appears in any response or log")
        env_in_image = docker("image", "inspect", IMAGE, "--format", "{{json .Config.Env}}").stdout
        check("GEMINI_API_KEY" not in env_in_image, "the image itself has no GEMINI_API_KEY (given at run time only)")

        print("\n7. Persistence")
        docker("restart", names[0])
        check(wait_healthy(port), "healthy again after docker restart")
        check(stored_runs(port) == before + 1, "run still stored after docker restart")
        docker("rm", "-f", names[0])
        port2 = free_port()
        start(names[1], port2, workdir, key)
        check(wait_healthy(port2), "a brand-new container started on the same folder")
        check(stored_runs(port2) == before + 1, "run still stored in the brand-new container")
        check((workdir / "data" / "results.db").exists(), "results.db is on the host disk, outside the container")
        docker("rm", "-f", names[1])

        print("\n8. Networking")
        port3 = free_port()
        docker("run", "-d", "--name", names[2], "-p", f"127.0.0.1:{port3}:8000", "--entrypoint", "python", IMAGE,
               "scripts/serve_api.py")      # WITHOUT --container: listens on the container's own 127.0.0.1
        time.sleep(5)
        inside = docker("exec", names[2], "python", "-c",
                        "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)",
                        check_rc=False).stdout.strip()
        check(inside == "200", "without --container: the server runs, reachable INSIDE the container", inside)
        check(not wait_healthy(port3, seconds=5), "without --container: NOT reachable from this computer")
        docker("rm", "-f", names[2])
    finally:
        for name in names:
            docker("rm", "-f", name, check_rc=False)
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        raise SystemExit(f"{len(failures)} check(s) FAILED: " + "; ".join(failures))
    print("All Docker checks passed. No Gemini request was sent; the temporary folder was deleted.")


if __name__ == "__main__":
    main()

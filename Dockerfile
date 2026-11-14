# AgentBench-Lite API image (Phase 11.1).
#
# Build:  docker build -t agentbench-api .
# Run:    docker run --rm -p 127.0.0.1:8000:8000 -v "${PWD}/data:/app/data" -v "${PWD}/results:/app/results" agentbench-api
#         (PowerShell; see docs/docker.md for the full commands, real runs and the API key)
#
# What is NOT in this image, on purpose: .env / API keys (given at run time with --env-file), your
# databases (shared from your disk with -v, so they survive the container), tests, the dashboard,
# .venv, node_modules and git history. .dockerignore enforces this.

# Small official Python image: Debian without compilers and docs. All our dependencies ship ready-made
# wheels, so nothing needs compiling.
FROM python:3.12-slim

# Don't write .pyc files into the image; print logs immediately (no buffering), so `docker logs` is live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Every relative path in the project ("data/results.db", "data/shop.db", "results/") is relative to here.
WORKDIR /app

# Install the package with only the extras the server needs: api (FastAPI, Uvicorn) and gemini (needed
# only if you later enable real runs). Not "dev": pytest is not needed to SERVE.
# A normal (non-editable) install: the code is copied into site-packages; pyproject.toml lists the JSON
# files that must come along.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".[api,gemini]" && rm -rf src build

COPY scripts ./scripts

# The server never runs as root: if anything ever went wrong inside it, it could not change the system
# files of the container. scripts/docker-entrypoint.sh starts as root only to pick the user: the OWNER of
# your shared data/ folder (Linux), else this agentbench user (Docker Desktop). Then it hands over.
RUN useradd --create-home --uid 10001 agentbench \
    && mkdir -p /app/data /app/results \
    && chown agentbench:agentbench /app/data /app/results

# Where results live. Mount your own folders here, or they disappear with the container.
VOLUME ["/app/data", "/app/results"]

# Documentation only: the port the server listens on INSIDE the container. Publishing is decided by
# `docker run -p` - use 127.0.0.1:8000:8000 so only this computer can reach it.
EXPOSE 8000

# Docker asks this every 30 s; `docker ps` then shows "healthy" or "unhealthy". Uses Python, so no
# curl needs to be installed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

# ENTRYPOINT = the fixed part; CMD = default extra options you can replace at `docker run`. Real runs are
# OFF unless you add --allow-real-runs yourself, e.g.  docker run ... agentbench-api --allow-real-runs
# (`sh script` instead of running the file directly: it works even if the execute bit was lost on Windows.)
ENTRYPOINT ["sh", "scripts/docker-entrypoint.sh", "--container"]
CMD []

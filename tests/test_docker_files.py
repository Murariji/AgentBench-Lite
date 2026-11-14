"""Phase 11.1: the Docker rules, checked WITHOUT Docker (so they run in every pytest run).

The real build-and-run proof is scripts/docker_check_api.py (needs Docker Desktop). These tests guard the
rules that must never regress: where the server listens, what may enter the image, and that the package
still ships its JSON files when installed normally (as the image does).
"""

import subprocess
import sys
import tomllib
from fnmatch import fnmatch
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from agentbench.api.app import CONTAINER_HOST, LOCAL_HOST, listen_host, running_in_container  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
IGNORE_RULES = [line.strip() for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]


# ---------- where the server listens -------------------------------------------------------------------

def test_without_container_flag_it_is_always_local():
    assert listen_host(False) == LOCAL_HOST == "127.0.0.1"
    assert listen_host(False, in_container=True) == LOCAL_HOST      # even inside Docker: opt-in only


def test_container_flag_inside_a_container_listens_on_all_container_interfaces():
    assert listen_host(True, in_container=True) == CONTAINER_HOST == "0.0.0.0"


def test_container_flag_outside_a_container_is_refused():
    with pytest.raises(ValueError, match="only for running inside a Docker container"):
        listen_host(True, in_container=False)


def test_container_detection_uses_the_engine_marker_files(tmp_path):
    marker = tmp_path / ".dockerenv"
    assert running_in_container([str(marker)]) is False
    marker.touch()
    assert running_in_container([str(marker)]) is True


@pytest.mark.skipif(running_in_container(), reason="this test is about running OUTSIDE a container")
def test_serve_api_refuses_container_flag_on_this_computer():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_api.py"), "--container"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60, encoding="utf-8")
    assert out.returncode != 0 and "only for running inside a Docker container" in out.stderr


# ---------- what may enter the image (.dockerignore) ---------------------------------------------------

def test_dockerignore_is_an_allow_list():
    assert IGNORE_RULES[0] == "*", "first ignore everything, then allow back only what is needed"
    allowed = {rule[1:].rstrip("/") for rule in IGNORE_RULES if rule.startswith("!")}
    assert allowed == {"pyproject.toml", "README.md", "LICENSE", "src", "scripts"}


@pytest.mark.parametrize("pattern", ["**/.env", "**/.env.*", "**/*.db", "**/__pycache__"])
def test_dockerignore_excludes_secrets_databases_and_caches_inside_allowed_folders(pattern):
    assert pattern in IGNORE_RULES


# ---------- the Dockerfile -------------------------------------------------------------------------------

def test_dockerfile_uses_python_312_and_never_copies_everything():
    assert "FROM python:3.12-slim" in DOCKERFILE
    copies = [line for line in DOCKERFILE.splitlines() if line.startswith("COPY")]
    assert copies and not any(line.split()[1] == "." for line in copies), "no `COPY . .`: copy named paths only"


def test_dockerfile_has_no_secrets():
    instructions = [line for line in DOCKERFILE.splitlines() if not line.lstrip().startswith("#")]
    assert not any("GEMINI_API_KEY" in line or ".env" in line for line in instructions)


ENTRYPOINT_SCRIPT = (ROOT / "scripts" / "docker-entrypoint.sh").read_bytes()


def test_entrypoint_always_hands_over_to_a_normal_user():
    """Root is used only to choose the user; every way of starting the server drops root first."""
    text = ENTRYPOINT_SCRIPT.decode("utf-8")
    starts = [line.strip() for line in text.splitlines() if line.strip().startswith("exec")]
    assert len(starts) == 2
    assert starts[1].startswith('exec setpriv --reuid="$run_uid" --regid="$run_gid" --clear-groups')
    assert 'if [ "$(id -u)" != "0" ]' in text      # the other start is only for an already non-root user
    assert "DEFAULT_UID=10001" in text


def test_entrypoint_never_takes_over_a_folder_that_holds_files():
    text = ENTRYPOINT_SCRIPT.decode("utf-8")
    assert 'if [ -z "$(ls -A "$dir")" ]; then' in text and "chown -R" not in text


def test_entrypoint_keeps_unix_line_endings():
    assert b"\r" not in ENTRYPOINT_SCRIPT, "CRLF breaks sh inside the container"
    assert "*.sh text eol=lf" in (ROOT / ".gitattributes").read_text(encoding="utf-8")


def test_dockerfile_starts_the_server_in_container_mode_with_real_runs_off():
    entry = next(line for line in DOCKERFILE.splitlines() if line.startswith("ENTRYPOINT"))
    assert '"scripts/docker-entrypoint.sh"' in entry and '"--container"' in entry
    assert "--allow-real-runs" not in entry
    assert next(line for line in DOCKERFILE.splitlines() if line.startswith("CMD")) == "CMD []"


def test_dockerfile_keeps_results_in_volumes():
    assert 'VOLUME ["/app/data", "/app/results"]' in DOCKERFILE


# ---------- the package ships its data files in a normal install ----------------------------------------

def test_every_non_python_package_file_is_listed_as_package_data():
    """The image does a normal `pip install .`; a file not listed here would silently be missing."""
    patterns = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["setuptools"]["package-data"]["agentbench"]
    package = ROOT / "src" / "agentbench"
    data_files = [p.relative_to(package).as_posix() for p in package.rglob("*")
                  if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts]
    assert data_files, "expected contract.json and the registrations"
    missing = [f for f in data_files if not any(fnmatch(f, pattern) for pattern in patterns)]
    assert not missing, f"add these to [tool.setuptools.package-data]: {missing}"

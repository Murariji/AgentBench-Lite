"""Phase 9.3: CORS (incl. preflight), the 64 KB body limit (incl. chunked bodies), no-cache, the index,
OpenAPI examples that cannot bypass the gates, and the startup database check. Offline only.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentbench.api import create_app  # noqa: E402
from agentbench.api.app import RUN_EXAMPLES, check_startup, validate_origins  # noqa: E402
from agentbench.api.middleware import MAX_BODY_BYTES  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ["http://localhost:5173", "http://127.0.0.1:5173"]
PREFLIGHT = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}


class NeverCalled:
    calls = 0

    def __call__(self):
        NeverCalled.calls += 1
        raise AssertionError("the real factory must not be called")


@pytest.fixture(scope="module")
def shop_db(tmp_path_factory):
    return build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")


@pytest.fixture
def client(tmp_path, shop_db):
    app = create_app(tmp_path / "results.db", shop_db_path=shop_db, recovery_dir=tmp_path / "rec",
                     real_llm_factory=NeverCalled(), sleep=lambda s: None)
    return TestClient(app, raise_server_exceptions=False)


# ---------- CORS ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("origin", ALLOWED)
def test_preflight_from_the_dashboard_origins(client, origin):
    r = client.options("/runs", headers={"Origin": origin, **PREFLIGHT})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin
    assert set(r.headers["access-control-allow-methods"].replace(" ", "").split(",")) == {"GET", "POST"}
    assert "access-control-allow-credentials" not in r.headers                 # no cookies / credentials


@pytest.mark.parametrize("origin", ALLOWED)
def test_actual_requests_from_the_dashboard_origins(client, origin):
    get = client.get("/suites", headers={"Origin": origin})
    post = client.post("/estimates", json={"agent": "careful", "suite": "shop"}, headers={"Origin": origin})
    assert get.status_code == 200 and get.headers["access-control-allow-origin"] == origin
    assert post.status_code == 200 and post.headers["access-control-allow-origin"] == origin


def test_a_disallowed_origin_gets_no_permission(client):
    evil = "http://evil.example"
    pre = client.options("/runs", headers={"Origin": evil, **PREFLIGHT})
    assert pre.status_code == 400 and "access-control-allow-origin" not in pre.headers
    get = client.get("/health", headers={"Origin": evil})
    assert "access-control-allow-origin" not in get.headers                   # the BROWSER will block reading it
    assert get.status_code == 200                                             # (CORS is not server security)


def test_other_methods_are_refused(client):
    r = client.options("/runs", headers={"Origin": ALLOWED[0], "Access-Control-Request-Method": "DELETE"})
    assert r.status_code == 400
    assert client.delete("/suites/zzzz9999").status_code == 405
    assert client.options("/runs").status_code == 405                         # OPTIONS without CORS: not an app method


@pytest.mark.parametrize("bad", ["*", "http://localhost:5173/", "http://x.example/path", "localhost:5173", "ftp://x"])
def test_only_exact_origins_are_accepted(bad, tmp_path):
    with pytest.raises(ValueError, match="invalid CORS origin"):
        validate_origins([bad])
    with pytest.raises(ValueError):
        create_app(tmp_path / "r.db", cors_origins=[bad])


def test_an_extra_origin_can_be_added(tmp_path, shop_db):
    app = create_app(tmp_path / "r.db", shop_db_path=shop_db, cors_origins=[*ALLOWED, "http://localhost:3000"])
    r = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


# ---------- the 64 KB body limit -------------------------------------------------------------------------

def chunked(total: int, size: int = 4096):
    """A body sent in chunks WITHOUT a Content-Length header."""
    sent = 0
    while sent < total:
        n = min(size, total - sent)
        sent += n
        yield b" " * n


def test_declared_too_large_is_413(client):
    r = client.post("/runs", content=b" " * (MAX_BODY_BYTES + 1), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    assert r.json()["error"]["details"] == {"limit_bytes": 65536}


def test_chunked_too_large_is_413_without_content_length(client):
    r = client.post("/runs", content=chunked(MAX_BODY_BYTES + 1), headers={"Content-Type": "application/json"})
    assert "content-length" not in r.request.headers                          # truly streamed
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_exactly_at_the_limit_is_not_413(client):
    body = b'{"agent": "careful"' + b" " * (MAX_BODY_BYTES - 21) + b"}x"         # 64 KB of invalid JSON
    assert len(body) == MAX_BODY_BYTES
    r = client.post("/runs", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"   # normal validation still works


def test_chunked_within_the_limit_still_works(client):
    payload = b'{"agent": "careful", "suite": "shop"}'
    r = client.post("/estimates", content=(payload[i:i + 5] for i in range(0, len(payload), 5)),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and r.json()["allowed"] is True


def test_413_still_carries_cors_headers_for_the_dashboard(client):
    r = client.post("/runs", content=chunked(MAX_BODY_BYTES + 10), headers={"Content-Type": "application/json",
                                                                             "Origin": ALLOWED[0]})
    assert r.status_code == 413 and r.headers["access-control-allow-origin"] == ALLOWED[0]


# ---------- small hardening items -------------------------------------------------------------------------

def test_live_data_is_never_cached(client):
    assert client.get("/runs").headers["cache-control"] == "no-store"
    assert client.post("/estimates", json={"agent": "careful"}).headers["cache-control"] == "no-store"
    assert "cache-control" not in client.get("/suites").headers


def test_index(client):
    assert client.get("/").json() == {"name": "AgentBench-Lite API", "version": "0.9.3", "docs": "/docs",
                                      "health": "/health", "real_runs_enabled": False, "local_only": "127.0.0.1"}


# ---------- OpenAPI examples: helpful, labelled, and unable to bypass anything ------------------------------

def test_examples_are_documented_and_labelled(client):
    spec = client.get("/openapi.json").json()
    for path in ("/runs", "/estimates"):
        examples = spec["paths"][path]["post"]["requestBody"]["content"]["application/json"]["examples"]
        assert set(examples) == {"scripted", "scripted_subset", "real_pilot_gated"}
        real = examples["real_pilot_gated"]
        assert real["summary"].startswith("REAL Gemini run") and "--allow-real-runs" in real["summary"]
        assert "ALL gates" in real["description"] and "sends nothing" in real["description"]


def test_executing_the_examples_cannot_bypass_the_gates(client):
    NeverCalled.calls = 0
    scripted = client.post("/runs", json=RUN_EXAMPLES["scripted_subset"]["value"])
    assert scripted.status_code == 202                                       # scripted: free, allowed
    real = client.post("/runs", json=RUN_EXAMPLES["real_pilot_gated"]["value"])
    assert real.status_code == 403 and real.json()["error"]["code"] == "real_runs_disabled"   # gates come first
    assert NeverCalled.calls == 0                                            # the real client was never built


# ---------- startup database check ---------------------------------------------------------------------------

def test_startup_check(tmp_path):
    assert check_startup(tmp_path / "fresh.db") is None
    foreign = tmp_path / "foreign.db"
    with sqlite3.connect(foreign) as conn:
        conn.execute("CREATE TABLE x (a)")
    assert "cannot use the results database" in check_startup(foreign)
    future = tmp_path / "future.db"
    with sqlite3.connect(future) as conn:
        conn.execute("PRAGMA user_version = 99")
    assert "version 99" in check_startup(future)


def serve(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_api.py"), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60, encoding="utf-8")


def test_the_server_refuses_to_start_on_an_unusable_database(tmp_path):
    foreign = tmp_path / "foreign.db"
    with sqlite3.connect(foreign) as conn:
        conn.execute("CREATE TABLE x (a)")
    out = serve("--db", foreign)
    assert out.returncode != 0 and "Not starting: cannot use the results database" in out.stderr


def test_the_server_refuses_a_wildcard_origin():
    out = serve("--cors-origin", "*")
    assert out.returncode != 0 and "invalid CORS origin" in out.stderr


def test_the_server_is_still_local_only():
    text = (ROOT / "scripts" / "serve_api.py").read_text(encoding="utf-8")
    assert 'HOST = "127.0.0.1"' in text and "--host" not in text

"""Phase 9.1: read-only API. FastAPI's TestClient calls the app in-process: no server, no network.

Every database is temporary; all agents are SCRIPTED test fixtures (not AI); no LLM is ever called.
Skipped entirely when the optional "api" extra (FastAPI) is not installed - the core never needs it.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentbench.api import create_app  # noqa: E402
from agentbench.benchmark import run_suite  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402
from agentbench.llm import FakeLLM, LLMError  # noqa: E402
from agentbench.storage import TABLES, ResultStore  # noqa: E402
from agentbench.suites import SHOP_HARD_TASKS, SHOP_TASKS, shop_registry  # noqa: E402
from agentbench.suites.shop_agents import scripted_agent, scripted_config  # noqa: E402
from agentbench.tools import ReadOnlySQLite  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATASET = "shop.db sha256:62143ef0c309"


@pytest.fixture(scope="module")
def suites(tmp_path_factory):
    """Six stored suites, oldest first."""
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as db:
        tools = shop_registry(db)

        def run(tasks, kind, name="shop", repeats=1, make_llm=None, **kw):
            return run_suite(tasks, scripted_config(kind), make_llm or scripted_agent(kind), tools, suite_name=name,
                             dataset=DATASET, repeats=repeats, progress=None, sleep=lambda s: None, **kw)

        def quota(task, repeat):
            if task.id == "shop-003":
                return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
            return scripted_agent("careful")(task, repeat)

        made = {
            "careful": run(SHOP_TASKS, "careful"),
            "sloppy": run(SHOP_TASKS, "sloppy"),
            "twice": run(SHOP_TASKS, "careful", repeats=2),
            "stopped": run(SHOP_TASKS, "careful", make_llm=quota, request_budget=80, min_requests_to_start=1),
            "hard": run(SHOP_HARD_TASKS, "careful", name="shop-hard"),
        }
    made["bare"] = made["careful"].model_copy(update={"suite_id": "bare0000" + "0" * 24, "tasks": []})
    return made


@pytest.fixture
def db(tmp_path, suites):
    path = tmp_path / "results.db"
    with ResultStore(path) as store:
        for name in ("careful", "sloppy", "twice", "stopped", "hard"):
            store.save(suites[name])
        bare = suites["bare"]
        store.save(bare.model_copy(update={"records": [], "skipped": []}))   # no tasks: cannot be analysed
    return path


@pytest.fixture
def client(db):
    return TestClient(create_app(db))


def is_error(response, status, code):
    body = response.json()
    assert response.status_code == status, body
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"}   # ONE shape
    assert body["error"]["code"] == code
    return body["error"]


# ---------- health, registrations --------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "schema_version": 3, "real_runs_enabled": False}


def test_registrations(client):
    regs = client.get("/registrations").json()
    assert [(r["suite"], r["version"]) for r in regs] == [("shop-hard", 1)]
    assert regs[0]["suite_fingerprint"] == "5f106feaff34" and len(regs[0]["tasks"]) == 9


# ---------- GET /suites: list + pagination -------------------------------------------------------------

def test_list_is_newest_first_with_pagination(client, suites):
    page = client.get("/suites?limit=2").json()
    assert page["pagination"] == {"limit": 2, "offset": 0, "total": 6, "returned": 2, "next_offset": 2}
    all_ids = [s["suite_id"] for s in client.get("/suites?limit=100").json()["items"]]
    # ORDER BY started_at DESC, then saved_at DESC ("bare" is a copy of "careful": same start, saved later)
    expected = [suites[n].suite_id for n in ("hard", "stopped", "twice", "sloppy", "bare", "careful")]
    assert all_ids == expected
    last = client.get("/suites?limit=2&offset=4").json()
    assert last["pagination"]["returned"] == 2 and last["pagination"]["next_offset"] is None
    beyond = client.get("/suites?offset=50").json()
    assert beyond["items"] == [] and beyond["pagination"]["next_offset"] is None


def test_list_item_fields(client, suites):
    items = {s["suite_id"]: s for s in client.get("/suites?limit=100").json()["items"]}
    sloppy = items[suites["sloppy"].suite_id]
    assert sloppy["kind"] == "scripted" and sloppy["short_id"] == suites["sloppy"].suite_id[:8]
    assert sloppy["pass_rate"] == {"passed": 6, "eligible": 10, "rate": 0.6, "text": "6/10 (60.0%)"}
    stopped = items[suites["stopped"].suite_id]
    assert stopped["complete"] is False and stopped["infra_errors"] == 1 and stopped["skipped"] == 7


def test_real_only_filter(client):
    assert client.get("/suites?real_only=true").json()["pagination"]["total"] == 0   # all scripted here


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
def test_invalid_pagination_is_422(client, query):
    error = is_error(client.get(f"/suites?{query}"), 422, "validation_error")
    assert error["details"]                                                     # says which field


# ---------- GET /suites/{id} ----------------------------------------------------------------------------

def test_suite_detail_by_full_and_short_id(client, suites):
    full = client.get(f"/suites/{suites['sloppy'].suite_id}").json()
    short = client.get(f"/suites/{suites['sloppy'].suite_id[:8]}").json()
    assert full == short
    assert full["kind"] == "scripted" and full["metrics"]["pass_rate"]["passed"] == 6
    assert len(full["runs"]) == 10 and all(isinstance(r["steps"], int) for r in full["runs"])
    assert "trace" not in full["runs"][0]                                       # summaries only: no trace here
    shop_003 = next(r for r in full["runs"] if r["task_id"] == "shop-003")
    assert shop_003["outcome"] == "failed" and shop_003["failed_checks"] == ["answer:number"]
    assert shop_003["retries"] == 0                                              # recorded: none happened
    assert full["registration"]["status"] == "unregistered"                      # shop is not registered


def test_registered_suite_detail(client, suites):
    hard = client.get(f"/suites/{suites['hard'].suite_id[:8]}").json()
    assert hard["registration"]["status"] == "matches" and hard["registration"]["version"] == 1
    assert hard["tools_fingerprint"] == "c1af5a87019e" and hard["config_fingerprint"]


def test_incomplete_suite_detail(client, suites):
    stopped = client.get(f"/suites/{suites['stopped'].suite_id[:8]}").json()
    assert stopped["complete"] is False and stopped["stop_reason"] == "quota_exhausted in shop-003"
    assert len(stopped["skipped"]) == 7 and stopped["metrics"]["infra_errors"] == 1


def test_unknown_suite_is_404(client):
    error = is_error(client.get("/suites/zzzz9999"), 404, "not_found")
    assert error["details"] == {"suite_id": "zzzz9999"}


@pytest.mark.parametrize("bad", ["ab", "abc", "abcd$", "a" * 65])
def test_invalid_suite_ids_are_422(client, bad):
    is_error(client.get(f"/suites/{bad}"), 422, "validation_error")


def test_ambiguous_short_id_is_409(tmp_path, suites):
    path = tmp_path / "amb.db"
    with ResultStore(path) as store:
        for i in (1, 2):
            store.save(suites["careful"].model_copy(update={"suite_id": f"abcd{i}" + "0" * 27,
                                                            "records": [], "skipped": []}))
    error = is_error(TestClient(create_app(path)).get("/suites/abcd"), 409, "ambiguous_id")
    assert "matches 2 suites" in error["message"]


# ---------- GET /suites/{id}/runs/{run_id} and /failures -------------------------------------------------

def test_run_detail_has_the_full_trace_and_analysis(client, suites):
    record = next(r for r in suites["sloppy"].records if r.task_id == "shop-003")
    body = client.get(f"/suites/{suites['sloppy'].suite_id[:8]}/runs/{record.run.run_id[:8]}").json()
    assert body["record"]["run"]["trace"]["steps"][0]["tool_call"]["tool_name"] == "sql_query"
    assert body["record"]["evaluation"]["checks"][1]["name"] == "answer:number"
    assert body["analysis"]["category"] == "wrong_result"


def test_unknown_run_is_404(client, suites):
    is_error(client.get(f"/suites/{suites['sloppy'].suite_id[:8]}/runs/ffffffff"), 404, "not_found")


def test_failures(client, suites):
    body = client.get(f"/suites/{suites['sloppy'].suite_id[:8]}/failures").json()
    assert body["analysis"]["category_counts"] == {"wrong_result": 4} and "not the model's reasoning" in body["note"]
    stopped = client.get(f"/suites/{suites['stopped'].suite_id[:8]}/failures").json()["analysis"]
    assert stopped["infra_errors"] == 1 and stopped["failed_runs"] == 0          # quota is not an agent failure


def test_failures_without_task_definitions_is_409(client):
    is_error(client.get("/suites/bare0000/failures"), 409, "not_analysable")


# ---------- tasks ---------------------------------------------------------------------------------------

def test_task_history_paginated(client):
    page = client.get("/tasks/shop-003/history?limit=2").json()
    assert page["task_id"] == "shop-003" and page["pagination"]["total"] == 5   # careful, sloppy, twice x2, stopped
    assert page["pagination"]["returned"] == 2 and page["pagination"]["next_offset"] == 2


def test_known_task_without_runs_is_an_empty_page(client):
    page = client.get("/tasks/hard-001/history").json()
    assert page["pagination"]["total"] == 1                                    # the scripted shop-hard run
    assert client.get("/tasks/hard-005/history").status_code == 200


def test_unknown_task_is_404(client):
    error = is_error(client.get("/tasks/nope-1/history"), 404, "not_found")
    assert "shop-hard" in error["details"]["known_suites"]
    is_error(client.get("/tasks/nope-1/measure"), 404, "not_found")


def test_invalid_task_id_is_422(client):
    is_error(client.get("/tasks/bad$id/history"), 422, "validation_error")


def test_measure(client):
    body = client.get("/tasks/shop-010/measure").json()
    assert body["groups"] and all(g["kind"] == "scripted" for g in body["groups"])
    assert any("not statistical proof" in line for line in body["limitations"])


# ---------- GET /compare ------------------------------------------------------------------------------

def test_fair_comparison(client, suites):
    body = client.get(f"/compare?ids={suites['careful'].suite_id[:8]}&ids={suites['sloppy'].suite_id[:8]}").json()
    assert body["fair"] is True and body["changed_dimensions"] == ["model"] and body["tools_status"] == "same"
    assert [t["task_id"] for t in body["tasks"] if t["differs"]] == ["shop-003", "shop-004", "shop-007", "shop-009"]
    assert any("Changed dimension: model" in line for line in body["conclusions"])
    assert len(body["metrics"]) == 2


def test_unfair_comparison_is_200_with_reasons(client, suites):
    body = client.get(f"/compare?ids={suites['careful'].suite_id[:8]}&ids={suites['twice'].suite_id[:8]}").json()
    assert body["fair"] is False and body["unfair_dimensions"] == ["repeats"]
    assert any("NOT A FAIR COMPARISON" in line for line in body["conclusions"])


def test_different_suites_cannot_be_compared(client, suites):
    error = is_error(client.get(f"/compare?ids={suites['careful'].suite_id[:8]}&ids={suites['hard'].suite_id[:8]}"),
                     409, "incompatible_comparison")
    assert "shop, shop-hard" in error["message"]


@pytest.mark.parametrize("query, status, code", [
    ("", 422, "validation_error"),                                   # no ids at all
    ("ids=zzzz9999", 422, "validation_error"),                      # only one
    ("&".join(f"ids=aaaa{i:04d}" for i in range(6)), 422, "validation_error"),   # more than 5
    ("ids=ab&ids=cdef", 422, "validation_error"),                    # invalid id
    ("ids=zzzz9999&ids=yyyy9999", 404, "not_found"),                 # unknown runs
])
def test_invalid_comparisons(client, query, status, code):
    is_error(client.get(f"/compare?{query}"), status, code)


def test_the_same_run_twice_is_422(client, suites):
    sid = suites["careful"].suite_id
    is_error(client.get(f"/compare?ids={sid}&ids={sid[:8]}"), 422, "validation_error")


# ---------- the rest of the contract -----------------------------------------------------------------

def test_unknown_route_and_wrong_method_use_the_error_shape(client):
    is_error(client.get("/nope"), 404, "not_found")
    is_error(client.post("/suites"), 405, "method_not_allowed")       # read-only: nothing can be created


def test_reads_never_change_the_database(client, db):
    def counts():
        with sqlite3.connect(db) as conn:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}   # allowlisted
    before = counts()
    for path in ("/suites", "/health", "/tasks/shop-003/history", "/tasks/shop-010/measure", "/registrations"):
        client.get(path)
    assert counts() == before


def test_restart_keeps_every_stored_result(db, suites):
    first = TestClient(create_app(db)).get("/suites?limit=100").json()
    restarted = TestClient(create_app(db)).get("/suites?limit=100").json()     # a brand-new app instance
    assert first == restarted and first["pagination"]["total"] == 6


def test_docs_page_and_schema_exist(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "AgentBench-Lite API"
    assert client.get("/docs").status_code == 200


def test_core_framework_works_without_fastapi():
    code = ("import sys; import agentbench, agentbench.benchmark, agentbench.storage, agentbench.report, "
            "agentbench.analysis, agentbench.registration, agentbench.measurement; "
            "assert 'fastapi' not in sys.modules, 'core imported fastapi'")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT).returncode == 0


def test_server_is_local_only():
    text = (ROOT / "scripts" / "serve_api.py").read_text(encoding="utf-8")
    assert 'HOST = "127.0.0.1"' in text and "--host" not in text

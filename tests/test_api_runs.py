"""Phase 9.2: background runs, the four real-run gates, concurrency, persistence, secrets.

The "real" runs here are FAKE: the app's real_llm_factory is injected with scripted FakeLLMs, so the
real Gemini client is NEVER constructed and nothing is sent anywhere. Temporary databases only.
"""

import json
import sqlite3
import threading
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import agentbench.runs as runs  # noqa: E402
from agentbench.api import create_app  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402
from agentbench.llm import FakeLLM, LLMError  # noqa: E402
from agentbench.registration import build_registration, check_suite, write_registration  # noqa: E402
from agentbench.report import load_json  # noqa: E402
from agentbench.storage import ResultStore  # noqa: E402
from agentbench.suites import SHOP_HARD_TASKS  # noqa: E402
from agentbench.suites.shop_agents import CAREFUL  # noqa: E402
from agentbench.tools import ReadOnlySQLite  # noqa: E402

FAKE_KEY = "AIzaFAKEfakeFAKEfake1234567890abcdef"
REAL_PILOT = {"agent": "gemini", "suite": "shop-hard", "tasks": ["hard-001", "hard-007"], "budget": 25,
              "confirm": True}


@pytest.fixture(autouse=True)
def real_client_is_forbidden(monkeypatch):
    """Safety net for EVERY test in this file: building the real Gemini client fails the test."""
    import agentbench.api.app as api_app

    def forbidden():
        raise AssertionError("a test tried to build the REAL Gemini client")
    monkeypatch.setattr(runs, "gemini_client", forbidden)
    monkeypatch.setattr(api_app, "gemini_client", forbidden)


def test_the_safety_net_works():
    import agentbench.api.app as api_app
    with pytest.raises(AssertionError, match="REAL Gemini client"):
        api_app.default_real_llm_factory()               # the server's default factory is blocked in tests


@pytest.fixture(scope="module")
def shop_db(tmp_path_factory):
    return build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")


class FakeReal:
    """Stands in for the real Gemini factory. Counts calls; can block a task until released."""

    def __init__(self, scripts=None, block=None, fail=None):
        self.calls = 0
        self.scripts = scripts or {}
        self.block = block                   # task id whose first request waits for `release`
        self.fail = fail                     # an exception raised when the factory is called
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self):
        self.calls += 1
        if self.fail:
            raise self.fail
        outer = self

        class Blocking(FakeLLM):
            def __init__(self, task_id, responses):
                super().__init__(responses)
                self.task_id = task_id

            def generate(self, messages, tools, system_prompt=None):
                if self.task_id == outer.block and not outer.release.is_set():
                    outer.started.set()
                    assert outer.release.wait(10), "test never released the blocked task"
                return super().generate(messages, tools, system_prompt)

        return "gemini-test", lambda task, repeat: Blocking(task.id, self.scripts.get(task.id, CAREFUL[task.id]))


def make(tmp_path, shop_db, *, allow=False, fake=None, db=None, max_budget=100):
    app = create_app(db or tmp_path / "results.db", allow_real_runs=allow, max_real_budget=max_budget,
                     real_llm_factory=fake or FakeReal(), shop_db_path=shop_db,
                     recovery_dir=tmp_path / "recovery", sleep=lambda s: None)
    return app, TestClient(app, raise_server_exceptions=False)


def wait(client, job_id, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/runs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish: {job}")


def error(response, status, code):
    body = response.json()
    assert response.status_code == status, body
    assert set(body) == {"error"} and body["error"]["code"] == code
    return body["error"]


# ---------- scripted runs: the full lifecycle ------------------------------------------------------

def test_scripted_run_lifecycle(tmp_path, shop_db):
    app, client = make(tmp_path, shop_db)
    response = client.post("/runs", json={"agent": "careful", "suite": "shop-hard"})
    assert response.status_code == 202 and response.headers["Location"] == f"/runs/{response.json()['job_id']}"
    started = response.json()
    assert started["status"] in ("queued", "running") and started["kind"] == "scripted"
    assert started["total_tasks"] == 9 and "lost when the server stops" in started["note"]
    job = wait(client, started["job_id"])
    assert job["status"] == "finished" and job["saved"] is True and job["recovery_path"] is None
    assert (job["completed_tasks"], job["total_tasks"], job["percent"], job["current_task"]) == (9, 9, 100.0, None)
    assert job["summary"]["pass_rate"] == "9/9 (100.0%)" and job["summary"]["complete"] is True
    assert sum(line.startswith("[") for line in job["progress"]) == 9
    stored = client.get(f"/suites/{job['suite_id']}").json()                 # persisted in SQLite
    assert stored["kind"] == "scripted" and stored["registration"]["status"] == "matches"


def test_structured_progress_while_running(tmp_path, shop_db):
    fake = FakeReal(block="hard-007")
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    job_id = client.post("/runs", json=REAL_PILOT).json()["job_id"]
    assert fake.started.wait(10)                                               # hard-001 done, hard-007 waiting
    job = client.get(f"/runs/{job_id}").json()
    assert job["status"] == "running" and job["kind"] == "real"
    assert (job["completed_tasks"], job["total_tasks"], job["percent"]) == (1, 2, 50.0)
    assert (job["current_task"], job["current_repeat"]) == ("hard-007", 1)
    assert job["progress"][0].startswith("[1/2] hard-001: PASSED") and job["saved"] is None   # not finished yet
    fake.release.set()
    assert wait(client, job_id)["status"] == "finished"


# ---------- the four real-run gates -------------------------------------------------------------------

def test_real_runs_disabled_is_403_and_the_factory_is_never_called(tmp_path, shop_db):
    fake = FakeReal()
    app, client = make(tmp_path, shop_db, allow=False, fake=fake)
    e = error(client.post("/runs", json=REAL_PILOT), 403, "real_runs_disabled")
    assert "--allow-real-runs" in e["message"]
    assert fake.calls == 0 and client.get("/runs").json()["items"] == []      # no job, no client
    assert client.get("/health").json()["real_runs_enabled"] is False


@pytest.mark.parametrize("change, status, code", [
    ({"confirm": False}, 422, "confirmation_required"),
    ({"budget": None}, 422, "budget_required"),
    ({"budget": 101}, 422, "budget_too_high"),
    ({"budget": 0}, 422, "validation_error"),
    ({"tasks": ["hard-999"]}, 422, "validation_error"),
    ({"suite": "nope"}, 422, "validation_error"),
    ({"repeats": 0}, 422, "validation_error"),
    ({"repeats": 11}, 422, "validation_error"),
    ({"agent": "gpt"}, 422, "validation_error"),
    ({"surprise": 1}, 422, "validation_error"),                               # unknown fields are rejected
])
def test_each_gate_and_input_check(tmp_path, shop_db, change, status, code):
    fake = FakeReal()
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    error(client.post("/runs", json={**REAL_PILOT, **change}), status, code)
    assert fake.calls == 0


def test_registration_mismatch_is_409_for_real_runs_only(tmp_path, shop_db, monkeypatch):
    with ReadOnlySQLite(shop_db) as db:
        from agentbench.suites import shop_registry
        tools = shop_registry(db).specs()
    stale = [t.model_copy(update={"expected_answer": "1"}) if t.id == "hard-001" else t for t in SHOP_HARD_TASKS]
    write_registration(build_registration("shop-hard", 1, stale, tools, dataset=None, git_head=None,
                                          source_committed=None), tmp_path / "regs")
    monkeypatch.setattr(runs, "check_suite",
                        lambda *a, **kw: check_suite(*a, **{**kw, "directory": tmp_path / "regs"}))
    fake = FakeReal()
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    e = error(client.post("/runs", json=REAL_PILOT), 409, "registration_mismatch")
    assert "DIFFERS from shop-hard v1" in e["message"] and fake.calls == 0
    scripted = client.post("/runs", json={"agent": "careful", "suite": "shop-hard", "tasks": ["hard-001"]})
    assert scripted.status_code == 202                                         # scripted: allowed (like the CLI)
    wait(client, scripted.json()["job_id"])


def test_all_gates_passed_starts_a_real_run(tmp_path, shop_db):
    fake = FakeReal()
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    job = wait(client, client.post("/runs", json=REAL_PILOT).json()["job_id"])
    assert job["status"] == "finished" and fake.calls == 1 and job["budget"] == 25
    stored = client.get(f"/suites/{job['suite_id']}").json()
    assert stored["kind"] == "real" and stored["config"]["model"] == "gemini-test"
    assert stored["config"]["min_interval_seconds"] == 6.0 and stored["request_budget"] == 25   # CLI protections


# ---------- concurrency: one run at a time, even for simultaneous requests ----------------------------------

def test_simultaneous_requests_start_exactly_one_run(tmp_path, shop_db):
    fake = FakeReal(block="hard-001")
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    barrier, results = threading.Barrier(8), []

    def post():
        barrier.wait()                                                         # all 8 fire together
        results.append(client.post("/runs", json=REAL_PILOT))

    threads = [threading.Thread(target=post) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    codes = sorted(r.status_code for r in results)
    assert codes == [202] + [409] * 7, codes
    assert all(r.json()["error"]["code"] == "run_in_progress" for r in results if r.status_code == 409)
    blocked = client.post("/runs", json={"agent": "careful", "suite": "shop"})  # scripted runs wait too
    error(blocked, 409, "run_in_progress")
    fake.release.set()
    winner = next(r for r in results if r.status_code == 202).json()["job_id"]
    assert wait(client, winner)["status"] == "finished"
    assert client.post("/runs", json={"agent": "careful", "suite": "shop"}).status_code == 202   # free again


# ---------- incomplete vs failed ------------------------------------------------------------------------

def test_budget_cut_mid_task_is_incomplete_and_keeps_finished_runs(tmp_path, shop_db):
    # hard-001 uses 3 requests; 5 are left (enough to START hard-007), but this hard-007 needs 8: cut at the cap
    from agentbench.suites.shop_agents import _sql
    long = [_sql("SELECT 1")] * 6 + CAREFUL["hard-007"]
    app, client = make(tmp_path, shop_db, allow=True, fake=FakeReal(scripts={"hard-007": long}))
    job = wait(client, client.post("/runs", json={**REAL_PILOT, "budget": 8}).json()["job_id"])
    assert job["status"] == "incomplete" and job["saved"] is True and job["error"] is None
    assert job["summary"]["requests"] == 8 and job["summary"]["passed"] == 1         # never above the cap
    assert job["summary"]["stop_reason"] == "budget_exhausted in hard-007"
    stored = client.get(f"/suites/{job['suite_id']}").json()
    assert [(r["task_id"], r["outcome"]) for r in stored["runs"]] == [("hard-001", "passed"), ("hard-007", "infra_error")]


def test_quota_exhaustion_is_incomplete_not_failed(tmp_path, shop_db):
    quota = LLMError("daily quota", kind="quota_exhausted", status_code=429)
    app, client = make(tmp_path, shop_db, allow=True, fake=FakeReal(scripts={"hard-001": [quota]}))
    job = wait(client, client.post("/runs", json=REAL_PILOT).json()["job_id"])
    assert job["status"] == "incomplete" and job["summary"]["infra_errors"] == 1 and job["summary"]["skipped"] == 1
    assert job["summary"]["passed"] == 0 and job["summary"]["evaluated"] == 0   # NOT counted as wrong answers


def test_retries_count_against_the_budget(tmp_path, shop_db):
    busy = LLMError("busy", kind="server", status_code=503)
    app, client = make(tmp_path, shop_db, allow=True,
                       fake=FakeReal(scripts={"hard-001": [busy, busy, *CAREFUL["hard-001"]]}))
    job = wait(client, client.post("/runs", json={**REAL_PILOT, "budget": 6}).json()["job_id"])
    # 2 retries + 3 good requests = 5 for hard-001 (passed); only 1 left, so hard-007 is not even started
    assert job["summary"]["requests"] == 5 and job["status"] == "incomplete" and job["summary"]["skipped"] == 1


def test_budget_too_small_to_start_is_incomplete_with_zero_requests(tmp_path, shop_db):
    app, client = make(tmp_path, shop_db, allow=True)
    job = wait(client, client.post("/runs", json={**REAL_PILOT, "budget": 4}).json()["job_id"])   # needs ~5 to start
    assert job["status"] == "incomplete" and job["summary"]["requests"] == 0 and job["summary"]["skipped"] == 2
    assert job["completed_tasks"] == 0 and job["saved"] is True


def test_unexpected_error_is_failed_and_never_leaks_a_secret(tmp_path, shop_db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    fake = FakeReal(fail=RuntimeError(f"could not connect with key={FAKE_KEY}"))
    app, client = make(tmp_path, shop_db, allow=True, fake=fake)
    job = wait(client, client.post("/runs", json=REAL_PILOT).json()["job_id"])
    assert job["status"] == "failed" and job["suite_id"] is None and job["saved"] is None
    assert "RuntimeError" in job["error"] and "[redacted]" in job["error"]
    for path in ("/runs", f"/runs/{job['job_id']}", "/health"):
        assert FAKE_KEY not in client.get(path).text
    assert client.post("/runs", json={"agent": "careful", "suite": "shop"}).status_code == 202   # lock released


def test_unexpected_server_error_has_no_traceback(tmp_path, shop_db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    app, client = make(tmp_path, shop_db)

    def broken():
        raise RuntimeError(f"secret {FAKE_KEY} inside")
    monkeypatch.setattr(app.state.jobs, "list", broken)
    response = client.get("/runs")
    e = error(response, 500, "internal_error")
    assert e["message"] == "unexpected server error (RuntimeError)" and FAKE_KEY not in response.text
    assert "Traceback" not in response.text


# ---------- persistence and recovery ---------------------------------------------------------------------

def test_failed_save_is_reported_honestly_with_a_usable_recovery_file(tmp_path, shop_db):
    broken = tmp_path / "not-ours.db"
    with sqlite3.connect(broken) as conn:
        conn.execute("CREATE TABLE something_else (x)")                         # not a results database
    app, client = make(tmp_path, shop_db, db=broken)
    job = wait(client, client.post("/runs", json={"agent": "careful", "suite": "shop-hard"}).json()["job_id"])
    assert job["status"] == "finished" and job["saved"] is False               # the run worked; saving did not
    assert "SchemaVersionError" in job["save_error"]
    recovered = load_json(job["recovery_path"])                                 # exact, absolute location
    assert recovered.suite_id == job["suite_id"] and len(recovered.records) == 9
    with ResultStore(tmp_path / "restored.db") as store:                       # ... and it restores fully
        assert store.load(store.save(recovered)) == recovered


def test_restart_loses_job_status_but_never_results(tmp_path, shop_db):
    db = tmp_path / "results.db"
    app1, client1 = make(tmp_path, shop_db, db=db)
    job = wait(client1, client1.post("/runs", json={"agent": "sloppy", "suite": "shop"}).json()["job_id"])
    app2, client2 = make(tmp_path, shop_db, db=db)                              # "the server restarted"
    e = error(client2.get(f"/runs/{job['job_id']}"), 404, "not_found")
    assert "kept in memory only" in e["message"] and "GET /suites" in e["message"]
    assert client2.get("/runs").json()["items"] == []
    assert client2.get(f"/suites/{job['suite_id']}").json()["metrics"]["passed_runs"] == 6   # result survived


# ---------- job ids and lists ------------------------------------------------------------------------------

def test_job_ids_and_list(tmp_path, shop_db):
    app, client = make(tmp_path, shop_db)
    job = wait(client, client.post("/runs", json={"agent": "careful", "suite": "shop"}).json()["job_id"])
    assert client.get(f"/runs/{job['job_id'][:8]}").json()["job_id"] == job["job_id"]   # short id
    error(client.get("/runs/ffffffff"), 404, "not_found")
    error(client.get("/runs/NOT-HEX!"), 422, "validation_error")
    page = client.get("/runs?limit=1").json()
    assert page["pagination"]["total"] == 1 and page["items"][0]["job_id"] == job["job_id"]


# ---------- POST /estimates never sends anything ------------------------------------------------------------

def test_estimates(tmp_path, shop_db):
    fake = FakeReal()
    app, client = make(tmp_path, shop_db, allow=False, fake=fake)
    scripted = client.post("/estimates", json={"agent": "careful", "suite": "shop-hard"}).json()
    assert scripted["allowed"] is True and scripted["estimate"] is None and scripted["runs"] == 9
    assert scripted["registration"]["status"] == "matches"
    real = client.post("/estimates", json=REAL_PILOT).json()
    assert real["allowed"] is False and any("disabled" in r for r in real["reasons"])
    assert real["estimate"]["worst_case_requests"] == 60 and real["registration"]["status"] == "subset"
    app2, client2 = make(tmp_path, shop_db, allow=True, fake=fake)
    assert client2.post("/estimates", json=REAL_PILOT).json()["allowed"] is True
    reasons = client2.post("/estimates", json={**REAL_PILOT, "confirm": False, "budget": 500}).json()["reasons"]
    assert len(reasons) == 2
    assert fake.calls == 0                                                      # estimates never build a client
    error(client.post("/estimates", json={"agent": "careful", "tasks": ["nope"]}), 422, "validation_error")

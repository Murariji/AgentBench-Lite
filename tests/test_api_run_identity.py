"""Contract change (2026-11-13): GET /suites items gain tasks_fingerprint, registration_status and scope,
so the dashboard can tell a SUBSET run from a full-suite run. Unknown is never assumed to be full.

Scripted runs (test fixtures, not AI) on temporary databases only; no API calls.
"""

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentbench.api import create_app  # noqa: E402
from agentbench.api.app import run_identity  # noqa: E402
from agentbench.benchmark import run_suite  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402
from agentbench.models import SuiteResult  # noqa: E402
from agentbench.storage import ResultStore  # noqa: E402
from agentbench.suites import SHOP_HARD_TASKS, SHOP_TASKS, shop_registry  # noqa: E402
from agentbench.suites.shop_agents import scripted_agent, scripted_config  # noqa: E402
from agentbench.tools import ReadOnlySQLite  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
DATASET = "shop.db sha256:62143ef0c309"          # what shop-hard v1 was registered with


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as db:
        tools = shop_registry(db)

        def run(tasks, name):
            return run_suite(tasks, scripted_config("careful"), scripted_agent("careful"), tools, suite_name=name,
                             dataset=DATASET, progress=None)

        edited = [t.model_copy(update={"expected_answer": "1"}) if t.id == "hard-001" else t for t in SHOP_HARD_TASKS]
        made = {
            "hard_full": run(SHOP_HARD_TASKS, "shop-hard"),
            "hard_pilot": run([t for t in SHOP_HARD_TASKS if t.id in ("hard-001", "hard-007")], "shop-hard"),
            "hard_differs": run(edited, "shop-hard"),
            "hard_differs_subset": run(edited[:2], "shop-hard"),
            "shop_full": run(SHOP_TASKS, "shop"),
            "shop_subset": run([t for t in SHOP_TASKS if t.id == "shop-010"], "shop"),
            "custom": run(SHOP_TASKS[:2], "my-own-suite"),          # a suite this code does not know
        }
    made["no_tasks"] = made["shop_full"].model_copy(update={"suite_id": "nodefs00" + "0" * 24, "tasks": []})
    return made


@pytest.fixture
def items(tmp_path, runs):
    path = tmp_path / "results.db"
    with ResultStore(path) as store:
        for name, suite in runs.items():
            store.save(suite if name != "no_tasks" else suite.model_copy(update={"records": [], "skipped": []}))
    page = TestClient(create_app(path)).get("/suites?limit=100").json()["items"]
    by_id = {s["suite_id"]: s for s in page}
    return {name: by_id[suite.suite_id] for name, suite in runs.items()}


@pytest.mark.parametrize("name, registration, scope", [
    ("hard_full", "matches", "full"),
    ("hard_pilot", "subset", "subset"),
    ("hard_differs", "differs", "full"),                 # all registered task ids, but a definition differs
    ("hard_differs_subset", "differs", "subset"),
    ("shop_full", "unregistered", "full"),
    ("shop_subset", "unregistered", "subset"),           # e.g. the A.3 shop-010 measurement
    ("custom", "unregistered", "unknown"),               # no suite to compare with: never assumed full
    ("no_tasks", "unknown", "unknown"),                  # task definitions not stored
])
def test_registration_status_and_scope(items, name, registration, scope):
    assert (items[name]["registration_status"], items[name]["scope"]) == (registration, scope)


def test_tasks_fingerprint_is_the_runs_own(items, runs):
    for name, suite in runs.items():
        expected = None if name == "no_tasks" else suite.tasks_fingerprint
        assert items[name]["tasks_fingerprint"] == expected
    assert items["hard_full"]["tasks_fingerprint"] == "ca11f5077756"           # = the registered v1 tasks
    assert items["hard_pilot"]["tasks_fingerprint"] != items["hard_full"]["tasks_fingerprint"]


def test_unknown_tasks_in_a_known_suite_are_not_called_a_subset(runs):
    odd = SHOP_TASKS[:1] + [SHOP_HARD_TASKS[0]]                                # a task shop does not contain
    identity = run_identity("shop", [t.id for t in odd], odd, None, None)
    assert identity["scope"] == "unknown" and identity["registration_status"] == "unregistered"


def test_historical_runs_are_judged_from_what_was_stored(tmp_path):
    path = tmp_path / "v1.db"                       # the genuine schema-1 database (Phase 8 fixture)
    with sqlite3.connect(path) as conn:
        conn.executescript((FIXTURES / "results_v1.sql").read_text(encoding="utf-8"))
    expected = [SuiteResult.model_validate(s)
                for s in json.loads((FIXTURES / "results_v1_suites.json").read_text(encoding="utf-8"))]
    page = TestClient(create_app(path)).get("/suites?limit=100").json()["items"]
    by_id = {s["suite_id"]: s for s in page}
    for suite in expected:                           # these stored their task definitions: checkable
        item = by_id[suite.suite_id]
        assert item["tasks_fingerprint"] == suite.tasks_fingerprint
        assert (item["registration_status"], item["scope"]) == ("unregistered", "full")


def test_the_light_identity_read_matches_a_full_load(tmp_path, runs):
    with ResultStore(tmp_path / "r.db") as store:
        store.save(runs["hard_pilot"])
        task_ids, tasks, tools, dataset = store.suite_identity(runs["hard_pilot"].suite_id)
        full = store.load(runs["hard_pilot"].suite_id)
    assert (task_ids, tasks, tools, dataset) == (full.task_ids, full.tasks, full.tools, full.dataset)


def test_nothing_else_in_the_list_changed(items):
    assert set(items["hard_full"]) >= {"suite_id", "short_id", "kind", "pass_rate", "complete", "scheduled_runs"}

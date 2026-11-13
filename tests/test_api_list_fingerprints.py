"""Contract change (2026-11-13, Step 10.3b): GET /suites items gain config_fingerprint and tools_fingerprint,
so the dashboard never joins runs of different configurations or tools into one chart line.

The values reuse the existing formulas (AgentConfig.config_fingerprint, models.tools_fingerprint) over STORED
data; runs stored without tools keep null (never reconstructed). Scripted fixtures only; no API calls.
"""

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentbench.api import create_app  # noqa: E402
from agentbench.benchmark import run_suite  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402
from agentbench.models import AgentConfig, SuiteResult  # noqa: E402
from agentbench.storage import ResultStore  # noqa: E402
from agentbench.suites import SHOP_TASKS, shop_registry  # noqa: E402
from agentbench.suites.shop_agents import scripted_agent, scripted_config  # noqa: E402
from agentbench.tools import ReadOnlySQLite  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def suites(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as db:
        tools = shop_registry(db)

        def run(config):
            return run_suite(SHOP_TASKS[:2], config, scripted_agent("careful"), tools, suite_name="shop", progress=None)

        base = scripted_config("careful")
        made = {
            "base": run(base),
            "renamed": run(base.model_copy(update={"name": "another-label"})),           # label only
            "other_prompt": run(AgentConfig(name=base.name, provider="fake", model=base.model,
                                            system_prompt="a different prompt")),
            "other_attempts": run(base.model_copy(update={"max_attempts": 1})),
        }
    made["no_tools"] = made["base"].model_copy(update={"suite_id": "notools0" + "0" * 24, "tools": None,
                                                       "records": [], "skipped": []})
    return made


@pytest.fixture
def listed(tmp_path, suites):
    with ResultStore(tmp_path / "r.db") as store:
        for suite in suites.values():
            store.save(suite)
    items = TestClient(create_app(tmp_path / "r.db")).get("/suites?limit=100").json()["items"]
    by_id = {s["suite_id"]: s for s in items}
    return {name: by_id[s.suite_id] for name, s in suites.items()}


def test_values_equal_the_existing_formulas(listed, suites):
    for name, suite in suites.items():
        assert listed[name]["config_fingerprint"] == suite.config.config_fingerprint     # the same property
        assert listed[name]["tools_fingerprint"] == suite.tools_fingerprint              # the same function


def test_label_only_changes_do_not_change_the_config_fingerprint(listed):
    assert listed["renamed"]["config_fingerprint"] == listed["base"]["config_fingerprint"]
    assert listed["other_prompt"]["config_fingerprint"] != listed["base"]["config_fingerprint"]
    assert listed["other_attempts"]["config_fingerprint"] != listed["base"]["config_fingerprint"]


def test_unrecorded_tools_stay_null(listed):
    assert listed["no_tools"]["tools_fingerprint"] is None                            # never invented
    assert listed["base"]["tools_fingerprint"] == "c1af5a87019e"


def test_deterministic_across_requests_and_restarts(tmp_path, suites):
    with ResultStore(tmp_path / "r.db") as store:
        store.save(suites["base"])
    first = TestClient(create_app(tmp_path / "r.db")).get("/suites").json()["items"][0]
    second = TestClient(create_app(tmp_path / "r.db")).get("/suites").json()["items"][0]
    assert (first["config_fingerprint"], first["tools_fingerprint"]) == \
           (second["config_fingerprint"], second["tools_fingerprint"])


def test_historical_runs_keep_null_tools_and_their_stored_config(tmp_path):
    path = tmp_path / "v2.db"                                       # the genuine schema-2 database (A.1 fixture)
    with sqlite3.connect(path) as conn:
        conn.executescript((FIXTURES / "results_v2.sql").read_text(encoding="utf-8"))
    expected = [SuiteResult.model_validate(s)
                for s in json.loads((FIXTURES / "results_v2_suites.json").read_text(encoding="utf-8"))]
    items = {s["suite_id"]: s for s in TestClient(create_app(path)).get("/suites?limit=100").json()["items"]}
    for suite in expected:
        assert items[suite.suite_id]["tools_fingerprint"] is None                   # not recorded then
        assert items[suite.suite_id]["config_fingerprint"] == suite.config.config_fingerprint


def test_list_and_details_agree(listed, tmp_path, suites):
    with ResultStore(tmp_path / "d.db") as store:
        store.save(suites["other_prompt"])
    client = TestClient(create_app(tmp_path / "d.db"))
    item = client.get("/suites").json()["items"][0]
    detail = client.get(f"/suites/{item['suite_id']}").json()
    assert (item["config_fingerprint"], item["tools_fingerprint"]) == \
           (detail["config_fingerprint"], detail["tools_fingerprint"])

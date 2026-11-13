"""Suite pre-registration (Step A.2): the registered shop-hard v1 must match today's suite exactly.

If test_shop_hard_matches_its_registration fails, shop-hard changed after it was registered.
Do NOT edit the registration: register a new version (python scripts/register_suite.py shop-hard --version 2).
"""

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.registration import (build_registration, differences, load_registration, suite_fingerprint,
                                     write_registration)
from agentbench.suites import SHOP_HARD_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite


@pytest.fixture(scope="module")
def tools(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as db:
        yield shop_registry(db).specs()


@pytest.fixture(scope="module")
def registered():
    return load_registration("shop-hard", 1)


def test_shop_hard_matches_its_registration(registered, tools):
    problems = differences(registered, SHOP_HARD_TASKS, tools)
    assert problems == [], "shop-hard changed after registration - register a NEW version: " + "; ".join(problems)


def test_registration_records_what_was_asked(registered):
    assert registered["suite"] == "shop-hard" and registered["version"] == 1
    assert len(registered["git_head"]) == 40 and registered["registered_at"]
    assert registered["tools"] == {"calculator": 2, "describe_table": 1, "list_tables": 1, "sql_query": 1}
    assert registered["suite_fingerprint"] == suite_fingerprint(registered["tasks_fingerprint"],
                                                                registered["tools_fingerprint"])
    answers = {t["id"]: (t["expected_answer"], t["answer_type"], t["abs_tolerance"], t["max_steps"])
               for t in registered["tasks"]}
    assert answers["hard-001"] == ("10995.5", "number", 0.0, 10)
    assert answers["hard-004"] == ("7.68", "number", 0.005, 10)
    assert answers["hard-008"] == ("Bengaluru", "contains", 0.0, 10)


def test_runs_use_the_same_tasks_fingerprint_as_the_registration(registered, tmp_path):
    with ReadOnlySQLite(build_shop_db(tmp_path / "shop.db")) as db:
        suite = run_suite(SHOP_HARD_TASKS, scripted_config("careful"), scripted_agent("careful"),
                          shop_registry(db), suite_name="shop-hard", progress=None)
    assert suite.tasks_fingerprint == registered["tasks_fingerprint"]   # stored runs are traceable to it
    assert suite.tools_fingerprint == registered["tools_fingerprint"]


# ---------- differences() names every kind of change -----------------------------------------------

@pytest.fixture
def record(tools):
    return build_registration("shop-hard", 1, SHOP_HARD_TASKS, tools, dataset="d", git_head=None,
                              source_committed=None)


def changed(task_id, **update):
    return [t.model_copy(update=update) if t.id == task_id else t for t in SHOP_HARD_TASKS]


def test_no_differences_for_the_same_suite(record, tools):
    assert differences(record, SHOP_HARD_TASKS, tools) == []


@pytest.mark.parametrize("update, expected", [
    ({"expected_answer": "10996"}, "hard-001.expected_answer: '10995.5' -> '10996'"),
    ({"abs_tolerance": 1.0}, "hard-001.abs_tolerance: 0.0 -> 1.0"),
    ({"max_steps": 8}, "hard-001.max_steps: 10 -> 8"),
    ({"prompt": "Reworded."}, "hard-001 definition changed (prompt or other fields)"),
])
def test_differences_name_the_change(record, tools, update, expected):
    problems = differences(record, changed("hard-001", **update), tools)
    assert expected in problems and any(p.startswith("tasks fingerprint") for p in problems)


def test_added_removed_tasks_and_tool_changes(record, tools):
    assert "hard-009 removed" in differences(record, SHOP_HARD_TASKS[:-1], tools)
    newer = [t.model_copy(update={"version": t.version + 1}) if t.name == "calculator" else t for t in tools]
    assert any(p.startswith("tools fingerprint") for p in differences(record, SHOP_HARD_TASKS, newer))


def test_a_registration_is_never_overwritten(record, tmp_path):
    write_registration(record, tmp_path)
    with pytest.raises(FileExistsError):
        write_registration(record, tmp_path)

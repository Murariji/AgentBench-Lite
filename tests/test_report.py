"""Scripted agents, reports, fair comparison and JSON export. Offline, temporary DB only."""

import json

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.llm import FakeLLM, LLMError
from agentbench.metrics import compute_metrics
from agentbench.models import AgentConfig
from agentbench.report import compare, export_json, format_report, load_json
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import SCRIPTS, scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def run(db, kind="careful", config=None, tasks=SHOP_TASKS, dataset="shop.db sha256:test", make_llm=None,
        repeats=1):
    return run_suite(tasks, config or scripted_config(kind), make_llm or scripted_agent(kind),
                     shop_registry(db), suite_name="shop", dataset=dataset, progress=None, repeats=repeats)


@pytest.fixture(scope="module")
def careful(db):
    return run(db, "careful")


@pytest.fixture(scope="module")
def sloppy(db):
    return run(db, "sloppy")


# ---------- scripted agents -----------------------------------------------------

def test_careful_agent_passes_everything(careful):
    assert str(compute_metrics(careful).pass_rate) == "10/10 (100.0%)"


def test_sloppy_agent_falls_into_exactly_the_four_traps(sloppy):
    failed = {r.task_id for r in sloppy.records if r.outcome == "failed"}
    assert failed == {"shop-003", "shop-004", "shop-007", "shop-009"}
    assert str(compute_metrics(sloppy).pass_rate) == "6/10 (60.0%)"


def test_scripts_cover_every_task_of_every_suite():
    from agentbench.suites import SUITES                     # shop + shop-hard (Step A.2)
    all_ids = {t.id for tasks in SUITES.values() for t in tasks}
    assert {t.id for t in SHOP_TASKS} < all_ids
    for kind, script in SCRIPTS.items():
        assert set(script) == all_ids, kind


def test_scripted_configs_are_labelled_as_fake():
    config = scripted_config("careful")
    assert config.provider == "fake" and config.is_scripted
    with pytest.raises(KeyError):
        scripted_config("genius")


# ---------- report -------------------------------------------------------------

def test_report_shows_kind_denominator_and_per_task_results(sloppy):
    report = format_report(sloppy)
    assert "SCRIPTED AGENT (not a real AI" in report
    assert "Pass rate  : 6/10 (60.0%)" in report
    assert "Status     : COMPLETE" in report
    assert "shop-003   medium  FAILED      (answer:number)" in report
    assert "max steps 8" in report and "sql_query" in report


def test_report_marks_incomplete_suites(db):
    def make_llm(task, repeat):
        if task.id == "shop-002":
            return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
        return scripted_agent("careful")(task, repeat)

    report = format_report(run(db, make_llm=make_llm))
    # Step 6.3 circuit breaker: after the quota error, shop-003..010 are skipped (not run)
    assert "Status     : INCOMPLETE - 1 infrastructure error(s), 8 skipped" in report
    assert "cover 1 of 10 scheduled runs" in report
    assert "Pass rate  : 1/1 (100.0%)" in report
    assert "INFRA_ERROR (quota_exhausted: not counted)" in report
    assert "shop-003   -       SKIPPED     (quota_exhausted in shop-002)" in report


def test_real_llm_configs_are_labelled_real(careful):
    real = careful.model_copy(update={"config": AgentConfig(
        name="g", provider="gemini", model="gemini-3.5-flash-lite", system_prompt="x")})
    assert "REAL LLM (gemini: gemini-3.5-flash-lite)" in format_report(real)


# ---------- comparison fairness -----------------------------------------------

def test_comparison_names_the_single_changed_dimension(careful, sloppy):
    text = compare([careful, sloppy])
    assert "Changed dimension: model (the only configuration difference)." in text
    assert "shop-003" in text and "<- differs" in text
    assert "NOT A FAIR COMPARISON" not in text
    assert "scripted agents only test the framework" in text


def test_comparison_warns_when_several_dimensions_changed(db, careful):
    other = run(db, "careful", config=AgentConfig(name="other", provider="fake", model="scripted-x",
                                                   system_prompt="a different prompt"))
    text = compare([careful, other])
    assert "WARNING: several dimensions changed (model, system prompt (hash))" in text


def test_comparison_with_no_config_change_is_run_to_run_variation(db, careful):
    again = run(db, "careful")
    assert "No configuration dimension changed" in compare([careful, again])


def test_different_tasks_or_dataset_is_not_fair(db, careful):
    fewer = run(db, "careful", tasks=SHOP_TASKS[:5])
    assert "NOT A FAIR COMPARISON" in compare([careful, fewer])
    other_data = run(db, "careful", dataset="shop.db sha256:different")
    text = compare([careful, other_data])
    assert "NOT A FAIR COMPARISON" in text and "dataset" in text.splitlines()[-3]


def test_unfair_comparison_never_explains_the_differences(db, careful, sloppy):
    # Found with real data: repeats 1 vs 3 printed "NOT A FAIR COMPARISON" AND then
    # "differences reflect run-to-run variation only" - two contradicting conclusions.
    twice = run(db, "careful", repeats=2)
    text = compare([careful, twice])
    assert "NOT A FAIR COMPARISON: these differ between runs: repeats." in text
    assert "run-to-run variation" not in text
    assert "Configuration: no dimension changed either" in text
    sloppy_twice = run(db, "sloppy", repeats=2)
    text = compare([careful, sloppy_twice])                       # unfair AND the model changed
    assert "Configuration: also changed: model." in text
    assert "Changed dimension" not in text                       # no attribution when unfair


def test_compare_needs_two_results(careful):
    with pytest.raises(ValueError):
        compare([careful])


# ---------- JSON export ---------------------------------------------------------

def test_export_contains_everything_and_loads_back(sloppy, tmp_path):
    path = export_json(sloppy, tmp_path)
    assert path.parent == tmp_path and path.name.startswith("shop_sloppy-script_")
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload["suite_result"]["records"][2]                     # shop-003
    assert record["task_id"] == "shop-003"
    assert record["run"]["trace"]["steps"][0]["tool_call"]["tool_name"] == "sql_query"  # traces
    assert record["evaluation"]["checks"][1]["reason"]                                   # checks
    assert payload["suite_result"]["config"]["model"] == "scripted-sloppy-v1"            # config
    assert payload["suite_result"]["started_at"] and payload["metrics"]["passed_runs"] == 6
    assert load_json(path) == sloppy                                    # lossless round trip


def test_export_never_overwrites(sloppy, tmp_path):
    first, second = export_json(sloppy, tmp_path), export_json(sloppy, tmp_path)
    assert first != second and first.exists() and second.exists()


def test_export_in_the_same_clock_tick_gets_a_suffix(sloppy, tmp_path, monkeypatch):
    # Force the collision that made the test above flaky on Windows: a frozen clock.
    import agentbench.report as report
    from datetime import datetime, timezone

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 13, 6, 37, 16, 779180, tzinfo=timezone.utc)

    monkeypatch.setattr(report, "datetime", FrozenClock)
    first, second, third = (export_json(sloppy, tmp_path) for _ in range(3))
    assert first.name == "shop_sloppy-script_20261113T063716779180Z.json"
    assert second.name.endswith("Z_2.json") and third.name.endswith("Z_3.json")
    assert load_json(first) == load_json(second) == load_json(third)    # nothing overwritten or lost


def test_load_rejects_foreign_json(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_json(bad)


def test_old_results_can_be_regraded_for_free(sloppy):
    # The export keeps the full task definitions, so evaluation can be redone with NO LLM calls.
    from agentbench.evaluators import evaluate
    tasks = {t.id: t for t in sloppy.tasks}
    regraded = [evaluate(tasks[r.task_id], r.run).passed for r in sloppy.records]
    assert regraded == [r.outcome == "passed" for r in sloppy.records]

"""Step 7.2: list_suites, task_history, resolve, save_with_recovery, results.py CLI. Offline."""

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.llm import FakeLLM, LLMError
from agentbench.metrics import compute_metrics
from agentbench.models import AgentConfig
from agentbench.report import export_json, load_json
from agentbench.storage import (DuplicateSuiteError, ResultStore, SuiteNotFoundError,
                                save_with_recovery)
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def run(shop, kind="careful", make_llm=None, config=None, **kwargs):
    return run_suite(SHOP_TASKS, config or scripted_config(kind), make_llm or scripted_agent(kind),
                     shop_registry(shop), suite_name="shop", progress=None, sleep=lambda s: None, **kwargs)


@pytest.fixture(scope="module")
def careful(shop):
    return run(shop, "careful").model_copy(update={"started_at": T0})


@pytest.fixture(scope="module")
def sloppy(shop):
    return run(shop, "sloppy", repeats=2).model_copy(update={"started_at": T0 + timedelta(hours=1)})


@pytest.fixture(scope="module")
def stopped(shop):
    """A 'real' (provider gemini) suite stopped by quota at shop-003 -> 7 skipped."""
    def make_llm(task, repeat):
        if task.id == "shop-003":
            return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
        return scripted_agent("careful")(task, repeat)
    config = AgentConfig(name="gemini-default", provider="gemini", model="gemini-test", system_prompt="p")
    return run(shop, make_llm=make_llm, config=config).model_copy(update={"started_at": T0 + timedelta(hours=2)})


@pytest.fixture
def store(tmp_path, careful, sloppy, stopped):
    with ResultStore(tmp_path / "results.db") as s:
        for suite in (sloppy, stopped, careful):            # saved in a DIFFERENT order than started
            s.save(suite)
        yield s


# ---------- list_suites ------------------------------------------------------------------

def test_newest_first(store, careful, sloppy, stopped):
    assert [s.suite_id for s in store.list_suites()] == [stopped.suite_id, sloppy.suite_id, careful.suite_id]


@pytest.mark.parametrize("name", ["careful", "sloppy", "stopped"])
def test_sql_counts_equal_compute_metrics(name, request, store):
    suite = request.getfixturevalue(name)
    row = next(s for s in store.list_suites() if s.suite_id == suite.suite_id)
    m = compute_metrics(suite)                               # two independent methods must agree
    assert (row.passed, row.failed, row.infra_errors, row.skipped, row.scheduled_runs) == \
           (m.passed_runs, m.failed_runs, m.infra_errors, m.skipped_runs, m.scheduled_runs)
    assert str(row.pass_rate) == str(m.pass_rate)
    assert row.total_llm_calls == m.total_llm_calls and row.complete == m.complete


def test_real_only_and_limit(store, stopped):
    assert [s.suite_id for s in store.list_suites(real_only=True)] == [stopped.suite_id]
    assert len(store.list_suites(limit=2)) == 2


def test_empty_database_lists_nothing(tmp_path):
    with ResultStore(tmp_path / "empty.db") as s:
        assert s.list_suites() == []


# ---------- task_history ---------------------------------------------------------------------

def test_task_history_newest_first_with_config_and_repeats(store, careful, sloppy, stopped):
    history = store.task_history("shop-003")
    assert [(h.suite_id, h.repeat, h.outcome) for h in history] == [
        (stopped.suite_id, 0, "infra_error"),
        (sloppy.suite_id, 0, "failed"), (sloppy.suite_id, 1, "failed"),
        (careful.suite_id, 0, "passed"),
    ]
    assert history[0].error_kind == "quota_exhausted" and history[0].model == "gemini-test"
    assert history[-1].config_name == "careful-script" and history[-1].final_answer == "3"
    assert history[-1].prompt_hash == careful.config.prompt_hash and history[-1].task_hash


def test_task_history_includes_skipped_runs(store, stopped):
    newest = store.task_history("shop-004")[0]
    assert newest.suite_id == stopped.suite_id and newest.outcome == "skipped"
    assert newest.reason == "quota_exhausted in shop-003" and newest.llm_calls is None


def test_task_history_shows_task_versions(shop, store):
    edited = [t.model_copy(update={"abs_tolerance": 2.0}) if t.id == "shop-010" else t for t in SHOP_TASKS]
    later = run_suite(edited, scripted_config("careful"), scripted_agent("careful"), shop_registry(shop),
                      suite_name="shop", progress=None)
    store.save(later)
    versions = {h.task_hash for h in store.task_history("shop-010")}
    assert len(versions) == 2                                # old and new definition, both traceable


def test_unknown_task_has_no_history(store):
    assert store.task_history("nope") == []


# ---------- short ids -------------------------------------------------------------------------

def test_resolve_short_ids(store, careful):
    assert store.resolve(careful.suite_id[:8]) == careful.suite_id
    with pytest.raises(SuiteNotFoundError):
        store.resolve("zzzz")
    with pytest.raises(SuiteNotFoundError):
        store.resolve("%")                                  # not a wildcard: plain text
    with pytest.raises(SuiteNotFoundError):
        store.resolve("")


def test_ambiguous_short_id(careful, tmp_path):
    with ResultStore(tmp_path / "r.db") as s:
        s.save(careful.model_copy(update={"suite_id": "abc1", "records": [], "skipped": []}))
        s.save(careful.model_copy(update={"suite_id": "abc2", "records": [], "skipped": []}))
        with pytest.raises(SuiteNotFoundError, match="matches 2"):
            s.resolve("abc")


# ---------- persistence failure is reported, never hidden --------------------------------------

def test_save_with_recovery_success(careful, tmp_path):
    outcome = save_with_recovery(careful, tmp_path / "r.db", tmp_path / "recovery")
    assert outcome.saved and outcome.error is None and outcome.recovery_path is None
    assert not (tmp_path / "recovery").exists()             # no backup needed


def test_failed_save_keeps_the_result_and_writes_a_recovery_copy(careful, tmp_path):
    broken = tmp_path / "not-ours.db"
    with sqlite3.connect(broken) as raw:
        raw.execute("CREATE TABLE something_else (x)")      # not an AgentBench database
    outcome = save_with_recovery(careful, broken, tmp_path / "recovery")
    assert not outcome.saved and "SchemaVersionError" in outcome.error
    assert load_json(outcome.recovery_path) == careful  # nothing lost
    assert careful.is_complete                               # the benchmark result is untouched


def test_unopenable_database_is_reported(careful, tmp_path):
    outcome = save_with_recovery(careful, tmp_path, tmp_path / "recovery")   # a FOLDER, not a file
    assert not outcome.saved and outcome.recovery_path.exists()


# ---------- import ------------------------------------------------------------------------------

def test_import_does_not_duplicate(careful, tmp_path):
    path = export_json(careful, tmp_path)
    with ResultStore(tmp_path / "r.db") as s:
        s.save(load_json(path))
        with pytest.raises(DuplicateSuiteError):
            s.save(load_json(path))
        assert len(s.list_suites()) == 1


def test_old_export_without_suite_id_imports_once(careful, tmp_path):
    path = export_json(careful, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["suite_result"]["suite_id"]                      # what exports looked like before 7.1
    path.write_text(json.dumps(data), encoding="utf-8")
    with ResultStore(tmp_path / "r.db") as s:
        first = load_json(path)
        s.save(first)
        with pytest.raises(DuplicateSuiteError):
            s.save(load_json(path))                      # the same stable id again
        assert s.load(first.suite_id).records == careful.records


# ---------- the CLI ------------------------------------------------------------------------------

def cli(*args, db):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "results.py"), "--db", str(db), *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)


def test_cli_import_list_show_compare_history(careful, sloppy, tmp_path):
    db = tmp_path / "cli.db"
    files = [export_json(careful, tmp_path), export_json(sloppy, tmp_path)]
    out = cli("import", *map(str, files), db=db)
    assert out.returncode == 0 and out.stdout.count("imported") == 2
    again = cli("import", str(files[0]), db=db)
    assert "already stored" in again.stdout

    listing = cli("list", db=db).stdout
    assert listing.index(sloppy.suite_id[:8]) < listing.index(careful.suite_id[:8])   # newest first
    assert "10/10 (100.0%)" in listing and "12/20 (60.0%)" in listing and "SCRIPTED" in listing

    shown = cli("show", careful.suite_id[:8], db=db).stdout
    assert f"Suite id   : {careful.suite_id}" in shown and "Pass rate  : 10/10" in shown

    compared = cli("compare", careful.suite_id[:8], sloppy.suite_id[:8], db=db).stdout
    assert "NOT A FAIR COMPARISON" in compared               # repeats differ: 1 vs 2

    history = cli("history", "shop-003", db=db).stdout
    assert history.count("FAILED") == 2 and history.count("PASSED") == 1


def test_cli_unknown_id_gives_a_clear_error(tmp_path):
    out = cli("show", "deadbeef", db=tmp_path / "x.db")
    assert out.returncode != 0 and "error: no suite id starts with 'deadbeef'" in out.stderr

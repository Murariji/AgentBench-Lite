"""ResultStore (Phase 7.1): lossless save/load, transactions, integrity, schema version.

Offline: scripted agents on a temporary shop DB; every results DB lives in tmp_path.
"""

import sqlite3

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import DEFAULT_DB_PATH, build_shop_db
from agentbench.llm import FakeLLM, LLMError
from agentbench.models import AgentConfig, SuiteResult
from agentbench.report import export_json, load_json
from agentbench.storage import (DEFAULT_RESULTS_DB, SCHEMA_VERSION, TABLES, DuplicateSuiteError,
                                ResultStore, SchemaVersionError, StorageError, SuiteNotFoundError)
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

EVIL = "x'; DROP TABLE suite_runs; --"


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def run(shop, kind="careful", make_llm=None, config=None, **kwargs):
    return run_suite(SHOP_TASKS, config or scripted_config(kind), make_llm or scripted_agent(kind),
                     shop_registry(shop), suite_name="shop", dataset="shop.db sha256:test",
                     progress=None, sleep=lambda s: None, **kwargs)


@pytest.fixture(scope="module")
def careful(shop):
    return run(shop, "careful")


@pytest.fixture(scope="module")
def sloppy(shop):
    return run(shop, "sloppy")


@pytest.fixture(scope="module")
def stopped(shop):
    """Incomplete: shop-003 hits quota_exhausted -> circuit breaker skips shop-004..010."""
    def make_llm(task, repeat):
        if task.id == "shop-003":
            return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
        return scripted_agent("careful")(task, repeat)
    return run(shop, make_llm=make_llm, request_budget=80, min_requests_to_start=1)


@pytest.fixture
def store(tmp_path):
    with ResultStore(tmp_path / "results.db") as s:
        yield s


def count(path, table: str) -> int:
    assert table in TABLES  # allowlisted identifier: table names can't be "?" parameters
    with sqlite3.connect(path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ---------- round trips: save -> load gives an IDENTICAL object -------------------

@pytest.mark.parametrize("name", ["careful", "sloppy", "stopped"])
def test_round_trip_is_lossless(name, request, store):
    suite = request.getfixturevalue(name)
    assert store.load(store.save(suite)) == suite


def test_incomplete_suite_keeps_infra_errors_and_skipped_runs(stopped, store):
    loaded = store.load(store.save(stopped))
    assert not loaded.is_complete and loaded.stop_reason == "quota_exhausted in shop-003"
    infra = loaded.records[2]
    assert infra.outcome == "infra_error" and infra.evaluation is None
    assert infra.run.error_kind == "quota_exhausted" and infra.run.status == "error"
    assert [s.task_id for s in loaded.skipped] == [f"shop-{i:03d}" for i in range(4, 11)]
    assert loaded.request_budget == 80


def test_traces_checks_and_tool_calls_survive(sloppy, store):
    loaded = store.load(store.save(sloppy))
    original, back = sloppy.records[2], loaded.records[2]          # shop-003, failed
    assert back.run.trace == original.run.trace                    # every step, SQL, timestamp
    assert back.evaluation.checks == original.evaluation.checks    # every check with its reason
    sql = [s.tool_call for s in back.run.trace.steps if s.tool_call]
    assert sql and sql[0].tool_name == "sql_query" and "query" in sql[0].arguments
    assert loaded.tasks_fingerprint == sloppy.tasks_fingerprint     # same tasks AND grading


def test_suite_without_task_definitions(careful, store):
    bare = careful.model_copy(update={"tasks": [], "suite_id": "bare"})
    assert store.load(store.save(bare)) == bare


# ---------- task versions: history stays interpretable -------------------------------

def test_task_definitions_are_snapshots_by_content(careful, shop, tmp_path):
    edited = [t.model_copy(update={"abs_tolerance": 5.0}) if t.id == "shop-010" else t for t in SHOP_TASKS]
    later = run_suite(edited, scripted_config("careful"), scripted_agent("careful"), shop_registry(shop),
                      suite_name="shop", progress=None)
    path = tmp_path / "r.db"
    with ResultStore(path) as store:
        store.save(careful)
        store.save(later)
        assert count(path, "task_versions") == 11                  # 10 shared + 1 new shop-010
        assert store.load(careful.suite_id).tasks == SHOP_TASKS    # the OLD definition is kept
        assert store.load(later.suite_id).tasks[-1].abs_tolerance == 5.0


# ---------- integrity ---------------------------------------------------------------

def test_duplicate_suite_is_rejected_and_nothing_changes(careful, tmp_path):
    path = tmp_path / "r.db"
    with ResultStore(path) as store:
        store.save(careful)
        before = {t: count(path, t) for t in TABLES}
        with pytest.raises(DuplicateSuiteError):
            store.save(careful)
        assert {t: count(path, t) for t in TABLES} == before


def test_same_runs_under_a_new_suite_id_are_rejected(careful, store):
    store.save(careful)
    with pytest.raises(StorageError, match="UNIQUE"):                # run_id is a primary key
        store.save(careful.model_copy(update={"suite_id": "copy"}))


def test_foreign_keys_reject_orphans(store, tmp_path):
    with sqlite3.connect(tmp_path / "results.db") as raw:
        raw.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            raw.execute("INSERT INTO steps (run_id, step_index, llm_output, timestamp)"
                        " VALUES ('no-such-run', 0, '', '2026-01-01T00:00:00+00:00')")


def test_malicious_text_is_stored_as_plain_text(careful, tmp_path):
    path = tmp_path / "r.db"
    config = careful.config.model_copy(update={"name": EVIL})
    evil = careful.model_copy(update={"suite_id": EVIL, "config": config, "stop_reason": EVIL})
    with ResultStore(path) as store:
        loaded = store.load(store.save(evil))
    assert loaded.config.name == EVIL and loaded.suite_id == EVIL
    assert count(path, "suite_runs") == 1                          # the table still exists


def test_indexes_exist(store, tmp_path):
    with sqlite3.connect(tmp_path / "results.db") as raw:
        names = {r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"idx_suite_runs_started", "idx_run_records_task", "idx_task_versions_task"} <= names


def test_inconsistent_nested_task_ids_are_refused(careful, store):
    record = careful.records[0]
    bad_run = record.run.model_copy(update={"trace": record.run.trace.model_copy(update={"task_id": "other"})})
    bad = careful.model_copy(update={"suite_id": "bad",
                                     "records": [record.model_copy(update={"run": bad_run})]})
    with pytest.raises(StorageError, match="trace.task_id"):
        store.save(bad)


# ---------- transactions: all or nothing --------------------------------------------

def test_crash_halfway_leaves_nothing(careful, tmp_path, monkeypatch):
    path = tmp_path / "r.db"
    with ResultStore(path) as store:
        original, calls = store._insert_record, []

        def crash_on_fifth(*args):
            calls.append(1)
            if len(calls) == 5:
                raise RuntimeError("simulated crash while saving")
            original(*args)

        monkeypatch.setattr(store, "_insert_record", crash_on_fifth)
        with pytest.raises(RuntimeError):
            store.save(careful)
        assert all(count(path, t) == 0 for t in TABLES)             # 4 records were rolled back
        assert not store.exists(careful.suite_id)
    assert careful.is_complete and len(careful.records) == 10      # the in-memory result is intact


def test_database_rule_violation_mid_save_rolls_back(careful, store, tmp_path):
    # A record for a task that was never scheduled: the FOREIGN KEY rejects it at record 10.
    # deep=True: a shallow copy would share (and corrupt) the run objects of the fixture
    bad_last = careful.records[-1].model_copy(deep=True, update={"task_id": "not-scheduled"})
    bad_last.run.__dict__["task_id"] = "not-scheduled"   # bypass validation to force a DB-level failure
    bad_last.run.trace.__dict__["task_id"] = "not-scheduled"
    bad_last.evaluation.__dict__["task_id"] = "not-scheduled"
    bad = careful.model_copy(update={"suite_id": "bad", "records": [*careful.records[:-1], bad_last]})
    with pytest.raises(StorageError, match="nothing saved"):
        store.save(bad)
    assert all(count(tmp_path / "results.db", t) == 0 for t in TABLES)


# ---------- schema version -------------------------------------------------------------

def test_new_database_gets_the_schema_version(store, tmp_path):
    with sqlite3.connect(tmp_path / "results.db") as raw:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_unknown_schema_version_is_refused(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as raw:
        raw.execute("PRAGMA user_version = 99")
    with pytest.raises(SchemaVersionError, match="version 99"):
        ResultStore(path)


def test_a_foreign_database_is_refused(tmp_path):
    path = tmp_path / "other.db"
    with sqlite3.connect(path) as raw:
        raw.execute("CREATE TABLE customers (id INTEGER)")
    with pytest.raises(SchemaVersionError, match="refusing"):
        ResultStore(path)


def test_reopening_keeps_the_data(careful, tmp_path):
    path = tmp_path / "r.db"
    with ResultStore(path) as store:
        store.save(careful)
    with ResultStore(path) as store:                               # a new connection, same file
        assert store.load(careful.suite_id) == careful


def test_unknown_suite_id(store):
    with pytest.raises(SuiteNotFoundError):
        store.load("does-not-exist")


# ---------- ids, old exports, separation ---------------------------------------------------

def test_every_suite_gets_its_own_id(careful, sloppy):
    assert careful.suite_id != sloppy.suite_id and len(careful.suite_id) == 32


def test_old_json_without_suite_id_gets_a_stable_id(careful, tmp_path):
    data = careful.model_dump(mode="json")
    del data["suite_id"]
    first, second = SuiteResult.model_validate(data), SuiteResult.model_validate(data)
    assert first.suite_id == second.suite_id != careful.suite_id   # same file -> same id


def test_json_export_and_database_agree(sloppy, store, tmp_path):
    assert store.load(store.save(load_json(export_json(sloppy, tmp_path)))) == sloppy


def test_results_db_is_separate_from_the_agents_database():
    assert DEFAULT_RESULTS_DB.resolve() != DEFAULT_DB_PATH.resolve()
    assert DEFAULT_RESULTS_DB.suffix == ".db"                       # git-ignored by *.db


def test_agent_sql_tool_cannot_attach_the_results_db(shop, store, tmp_path):
    results = (tmp_path / "results.db").as_posix()
    output = shop_registry(shop).execute("sql_query", {"query": f"ATTACH DATABASE '{results}' AS r"})
    assert output.error is not None                                 # only SELECT/WITH is allowed

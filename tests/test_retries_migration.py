"""Step 8.1: retry events in traces, and the results-DB migration from schema 1 to 2. Offline."""

import json
import sqlite3
from pathlib import Path

import pytest

import agentbench.storage as storage
from agentbench.benchmark import run_suite
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.models import AgentConfig, SuiteResult, Task
from agentbench.runner import AgentRunner, RetryPolicy
from agentbench.storage import SCHEMA_VERSION, TABLES, ResultStore, StorageError
from agentbench.tools import CalculatorTool, ToolRegistry

FIXTURES = Path(__file__).parent / "fixtures"
TASK = Task(id="add", prompt="2+2?", expected_answer="4", answer_type="number")


def busy(code=503, kind="server", **kw):
    return LLMError("busy", kind=kind, status_code=code, **kw)


def calc():
    return LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": "2+2"}))


def run(script, max_attempts=3):
    waits: list[float] = []
    runner = AgentRunner(FakeLLM(script), ToolRegistry([CalculatorTool()]),
                         retry=RetryPolicy(max_attempts=max_attempts), sleep=waits.append)
    return runner.run(TASK), waits


# ---------- retry events are recorded --------------------------------------------------

def test_no_errors_means_recorded_and_empty_not_unknown():
    result, _ = run([calc(), LLMResponse(text="4")])
    assert result.retries == []                                   # [] = recorded, none happened


def test_retry_that_succeeds():
    result, waits = run([busy(), calc(), LLMResponse(text="4")])
    [event] = result.retries
    assert (event.step_index, event.attempt, event.error_kind, event.status_code) == (0, 1, "server", 503)
    assert event.waited_seconds == waits[0] == 1.0 and event.succeeded
    assert result.status == "completed" and result.llm_calls == 3


def test_two_retries_on_the_second_step_both_succeed_eventually():
    result, waits = run([calc(), busy(), busy(), LLMResponse(text="4")])
    assert [(e.step_index, e.attempt, e.waited_seconds, e.succeeded) for e in result.retries] == \
           [(1, 1, 1.0, True), (1, 2, 2.0, True)]                 # backoff 1 s, then 2 s
    assert waits == [1.0, 2.0]


def test_exhausted_retries_are_marked_unsuccessful():
    result, _ = run([busy(), busy(), busy()])
    assert result.status == "error" and result.error_kind == "server" and result.llm_calls == 3
    # attempts 1 and 2 were retried; attempt 3 failed too, with no retry left (that's run.error)
    assert [(e.attempt, e.succeeded) for e in result.retries] == [(1, False), (2, False)]


def test_retry_after_and_request_id_are_kept():
    result, _ = run([busy(429, "rate_limit", retry_after=5.0, request_id="req-123"), LLMResponse(text="4")])
    [event] = result.retries
    assert event.waited_seconds == 5.0 and event.request_id == "req-123" and event.error_kind == "rate_limit"


def test_non_retryable_errors_are_not_retries():
    result, _ = run([LLMError("bad key", kind="auth", status_code=401)])
    assert result.retries == [] and result.error_kind == "auth"


# ---------- retries survive storage, and "unknown" stays unknown ------------------------------

def suite_with_retries():
    def make_llm(task, repeat):
        return FakeLLM([busy(), calc(), LLMResponse(text="4")])
    config = AgentConfig(name="c", provider="fake", model="m", system_prompt="p")
    return run_suite([TASK], config, make_llm, ToolRegistry([CalculatorTool()]), suite_name="s",
                     progress=None, sleep=lambda s: None)


def test_retries_round_trip(tmp_path):
    suite = suite_with_retries()
    with ResultStore(tmp_path / "r.db") as store:
        loaded = store.load(store.save(suite))
    assert loaded == suite and len(loaded.records[0].run.retries) == 1


def test_not_recorded_and_none_happened_stay_different(tmp_path):
    suite = suite_with_retries()
    record = suite.records[0]
    unknown = record.model_copy(update={"run": record.run.model_copy(update={"retries": None})})
    old_style = suite.model_copy(update={"suite_id": "old", "records": [unknown]})
    old_style.records[0].run.__dict__["run_id"] = "old-run"            # distinct primary key
    old_style.records[0].evaluation.__dict__["run_id"] = "old-run"
    with ResultStore(tmp_path / "r.db") as store:
        assert store.load(store.save(old_style)).records[0].run.retries is None   # NOT []


# ---------- migration 1 -> 2 on a genuine version-1 database ------------------------------------

def make_v1_db(path: Path) -> Path:
    """Recreate the database that the Phase 7 (schema 1) code wrote: see fixtures/make_results_v1_fixture.py."""
    with sqlite3.connect(path) as conn:
        conn.executescript((FIXTURES / "results_v1.sql").read_text(encoding="utf-8"))
    return path


def fixture_suites() -> list[SuiteResult]:
    return [SuiteResult.model_validate(s)
            for s in json.loads((FIXTURES / "results_v1_suites.json").read_text(encoding="utf-8"))]


def counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # t is from the TABLES allowlist
                for t in TABLES if t in names}


def version(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def test_fixture_really_is_version_1(tmp_path):
    path = make_v1_db(tmp_path / "v1.db")
    assert version(path) == 1 and "retries" not in counts(path)


def test_migration_keeps_every_stored_run(tmp_path):
    path = make_v1_db(tmp_path / "v1.db")
    before = counts(path)
    with ResultStore(path) as store:                                 # opening = upgrading
        for expected in fixture_suites():
            loaded = store.load(expected.suite_id)
            assert loaded == expected                                # identical after migration
            assert all(r.run.retries is None for r in loaded.records)   # unknown, NOT zero
        assert [s.passed for s in store.list_suites()] == [2, 6, 10]   # newest first: stopped, sloppy, careful
    assert version(path) == SCHEMA_VERSION == 2
    after = counts(path)
    assert after.pop("retries") == 0 and after == before             # nothing added or lost


def test_migrated_database_accepts_new_runs(tmp_path):
    path = make_v1_db(tmp_path / "v1.db")
    with ResultStore(path) as store:
        new = suite_with_retries()
        assert store.load(store.save(new)) == new                    # old and new side by side
        assert len(store.list_suites()) == 4


def test_fresh_and_migrated_databases_have_the_same_schema(tmp_path):
    def columns(path):
        with sqlite3.connect(path) as conn:
            return {t: conn.execute(f"PRAGMA table_info({t})").fetchall() for t in TABLES}
    ResultStore(tmp_path / "fresh.db").close()
    ResultStore(make_v1_db(tmp_path / "old.db")).close()
    assert columns(tmp_path / "fresh.db") == columns(tmp_path / "old.db")


def test_failed_migration_rolls_back_completely(tmp_path, monkeypatch):
    path = make_v1_db(tmp_path / "v1.db")
    before = counts(path)
    broken = storage.MIGRATIONS[1] + "\nINSERT INTO no_such_table VALUES (1);"   # fails at the END
    monkeypatch.setitem(storage.MIGRATIONS, 1, broken)
    with pytest.raises(StorageError, match="nothing was changed"):
        ResultStore(path)
    assert version(path) == 1 and counts(path) == before            # no retries table, same rows
    with sqlite3.connect(path) as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(run_records)")]
    assert "retries_recorded" not in cols                            # the ALTER TABLE was undone too
    monkeypatch.setitem(storage.MIGRATIONS, 1, broken.replace("INSERT INTO no_such_table VALUES (1);", ""))
    with ResultStore(path) as store:                                 # the fixed migration then works
        assert store.load(fixture_suites()[0].suite_id) == fixture_suites()[0]


def test_newer_version_is_refused(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 3")
    with pytest.raises(storage.SchemaVersionError, match="up to version 2"):
        ResultStore(path)

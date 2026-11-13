"""Step A.1: tool versions, canonical contract fingerprints, snapshots, comparison, migration 2 -> 3.

Offline. Scripted agents are TEST FIXTURES, not intelligent agents.
"""

import json
import sqlite3
from pathlib import Path

import pytest

import agentbench.storage as storage
from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.models import SuiteResult, ToolSpec, canonical_json, tools_fingerprint
from agentbench.report import compare, export_json, format_report, load_json, tool_changes
from agentbench.storage import SCHEMA_VERSION, TABLES, ResultStore, StorageError
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import CalculatorTool, ReadOnlySQLite, ToolRegistry
from agentbench.tools.base import Tool

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def run(shop, kind="careful", registry=None):
    return run_suite(SHOP_TASKS, scripted_config(kind), scripted_agent(kind), registry or shop_registry(shop),
                     suite_name="shop", dataset="shop.db sha256:test", progress=None)


@pytest.fixture(scope="module")
def careful(shop):
    return run(shop)


def spec(name="calculator", version=1, description="Evaluate an expression.", parameters=None):
    return ToolSpec(name=name, version=version, description=description,
                    parameters=parameters or {"type": "object", "properties": {"expression": {"type": "string"}}})


def with_tools(suite, tools, suite_id):
    return suite.model_copy(update={"tools": tools, "suite_id": suite_id})


# ---------- explicit versions -------------------------------------------------------------

def test_every_registered_tool_has_an_explicit_version(shop):
    specs = shop_registry(shop).specs()
    assert [s.name for s in specs] == ["calculator", "describe_table", "list_tables", "sql_query"]
    assert all(type(s.version) is int and s.version >= 1 for s in specs)


@pytest.mark.parametrize("bad", ["missing", 0, "1", True, 1.5])
def test_a_tool_without_a_valid_version_is_refused(bad):
    attrs = {"name": "t", "description": "d", "run": lambda self: "x"}
    if bad != "missing":
        attrs["version"] = bad
    tool_class = type("T", (Tool,), attrs)
    with pytest.raises(ValueError, match="explicit version"):
        ToolRegistry([tool_class()])


# ---------- canonical, deterministic fingerprints -----------------------------------------------

def test_canonical_json_ignores_key_order_and_spacing():
    assert canonical_json({"b": 1, "a": {"y": 2, "x": 3}}) == canonical_json({"a": {"x": 3, "y": 2}, "b": 1})
    assert canonical_json({"a": "₹"}) == '{"a":"₹"}'                     # no spaces, real Unicode


def test_contract_fingerprint_is_deterministic():
    reordered = spec(parameters={"properties": {"expression": {"type": "string"}}, "type": "object"})
    assert spec().contract_fingerprint == reordered.contract_fingerprint   # same contract, other key order


def test_contract_changes_change_the_contract_fingerprint():
    base = spec().contract_fingerprint
    assert spec(description="Evaluate an arithmetic expression.").contract_fingerprint != base
    assert spec(parameters={"type": "object", "properties": {"expr": {"type": "string"}}}).contract_fingerprint != base
    assert spec(version=2).contract_fingerprint == base                    # version is NOT part of the contract


def test_tools_fingerprint_covers_versions_and_ignores_order():
    a, b = spec("calculator"), spec("sql_query", description="Run SQL.")
    assert tools_fingerprint([a, b]) == tools_fingerprint([b, a])
    assert tools_fingerprint([spec(version=2), b]) != tools_fingerprint([a, b])   # a behaviour change
    assert tools_fingerprint(None) is None                                        # unknown stays unknown


# ---------- tripwires -----------------------------------------------------------------------------
# If one of these fails, a tool changed. Decide deliberately:
#   * behaviour changed -> raise that tool's `version`, then update the pins below;
#   * only the wording/schema changed -> update the contract pin (runs will show "contract changed").

PINNED_CONTRACTS = {             # contract fingerprints of the shop tools, version 1 (Step A.1)
    "calculator": "b6ed49cab787",
    "describe_table": "95015d83cc59",
    "list_tables": "d438d6e99a62",
    "sql_query": "caad37852689",
}
PINNED_SHOP_TOOLS = "2191990ea327"


def test_tripwire_contract_fingerprints(shop):
    specs = shop_registry(shop).specs()
    assert {s.name: s.contract_fingerprint for s in specs} == PINNED_CONTRACTS
    assert tools_fingerprint(specs) == PINNED_SHOP_TOOLS


# Representative behaviours of calculator VERSION 1. These cover only the cases listed here: they
# cannot detect every possible change in meaning. Step A.3 will change some of them on purpose -
# and must raise the calculator to version 2 when it does.
CALCULATOR_V1 = [
    ("2416098 / 150", "16107.32", None),
    ("(26 - 21) / 21 * 100", "23.809523809523807", None),
    ("round(16107.32)", None, "unsupported syntax: Call"),
    ("abs(-3)", None, "unsupported syntax: Call"),
    ("2 ** 101", None, "exponent too large (max 100)"),
    ("1 / 0", None, "division by zero"),
    ('__import__("os")', None, "unsupported syntax: Call"),
]


@pytest.mark.parametrize("expression, output, error", CALCULATOR_V1)
def test_tripwire_calculator_v1_behaviour(expression, output, error):
    assert CalculatorTool.version == 1, "calculator version changed: replace these v1 pins with the new version's"
    call = ToolRegistry([CalculatorTool()]).execute("calculator", {"expression": expression})
    assert (call.output, call.error) == (output, error)


# ---------- snapshots in suite results -----------------------------------------------------------

def test_suite_records_the_tool_snapshot(careful, shop):
    assert careful.tools == shop_registry(shop).specs() and careful.tools_fingerprint == PINNED_SHOP_TOOLS


def test_snapshot_survives_json_export(careful, tmp_path):
    assert load_json(export_json(careful, tmp_path)).tools == careful.tools


def test_old_json_without_tools_loads_as_unknown(careful):
    data = careful.model_dump(mode="json")
    del data["tools"]
    old = SuiteResult.model_validate(data)
    assert old.tools is None and old.tools_fingerprint is None              # unknown, not []


def test_report_shows_tools_or_not_recorded(careful):
    assert "Tools      : calculator v1, describe_table v1, list_tables v1, sql_query v1" in format_report(careful)
    old = careful.model_copy(update={"tools": None})
    assert "Tools      : not recorded (run stored before tool versions existed)" in format_report(old)


# ---------- comparison: same / changed / unknown -------------------------------------------------------

def test_same_tools_add_nothing(careful, shop):
    text = compare([careful, run(shop)])
    assert "Tools changed" not in text and "not recorded" not in text
    assert "No configuration dimension changed" in text


def test_changed_tool_version_is_the_changed_dimension(careful):
    v2 = [s.model_copy(update={"version": 2}) if s.name == "calculator" else s for s in careful.tools]
    text = compare([careful, with_tools(careful, v2, "v2")])
    assert "Changed dimension: tools (fingerprint) (the only configuration difference)." in text
    assert "calculator v1 -> v2" in text


def test_changed_contract_with_the_same_version_is_flagged(careful):
    edited = [s.model_copy(update={"description": s.description + " Now also rounds."}) if s.name == "calculator"
              else s for s in careful.tools]
    text = compare([careful, with_tools(careful, edited, "edited")])
    assert "calculator contract changed (description/parameters) with the SAME version v1" in text


def test_tools_and_model_changed_is_a_multi_change_warning(careful, shop):
    sloppy = run(shop, "sloppy")
    v2 = [s.model_copy(update={"version": 2}) if s.name == "calculator" else s for s in sloppy.tools]
    text = compare([careful, with_tools(sloppy, v2, "both")])
    assert "WARNING: several dimensions changed (model, tools (fingerprint))" in text


def test_unknown_tools_are_never_assumed_identical(careful, shop):
    old = with_tools(run(shop), None, "oldrun00")
    text = compare([careful, old])
    assert "WARNING: tools were not recorded for oldrun00" in text and "not assumed identical" in text
    assert "differences reflect run-to-run variation only" not in text      # the confident claim is gone
    assert "cannot be confirmed as run-to-run variation only" in text
    text = compare([careful, with_tools(run(shop, "sloppy"), None, "oldrun01")])
    assert "Changed dimension: model (the only RECORDED configuration difference; tools unknown)." in text


def test_tool_changes_lists_added_and_removed():
    assert tool_changes([spec("a")], [spec("b")]) == ["a removed (was v1)", "b added (v1)"]


# ---------- storage + migration 2 -> 3 ------------------------------------------------------------------

def test_tools_round_trip_and_are_stored_once(careful, shop, tmp_path):
    path = tmp_path / "r.db"
    with ResultStore(path) as store:
        assert store.load(store.save(careful)).tools == careful.tools
        store.save(run(shop))                                                   # same tools again
        v2 = [s.model_copy(update={"version": 2}) if s.name == "calculator" else s for s in careful.tools]
        other = run(shop)
        store.save(with_tools(other, v2, "v2-suite"))
        assert store.load("v2-suite").tools == v2
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tool_versions").fetchone()[0] == 5   # 4 shared + calculator v2


def test_not_recorded_and_empty_stay_different(careful, tmp_path):
    with ResultStore(tmp_path / "r.db") as store:
        unknown = with_tools(careful, None, "unknown")
        assert store.load(store.save(unknown)).tools is None


def load_fixture_db(path: Path, name: str) -> Path:
    with sqlite3.connect(path) as conn:
        conn.executescript((FIXTURES / f"{name}.sql").read_text(encoding="utf-8"))
    return path


def fixture_suites(name: str) -> list[SuiteResult]:
    return [SuiteResult.model_validate(s)
            for s in json.loads((FIXTURES / f"{name}_suites.json").read_text(encoding="utf-8"))]


def user_version(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


@pytest.mark.parametrize("name, old_version", [("results_v1", 1), ("results_v2", 2)])
def test_genuine_old_databases_upgrade_without_losing_anything(name, old_version, tmp_path):
    path = load_fixture_db(tmp_path / f"{name}.db", name)
    assert user_version(path) == old_version
    with ResultStore(path) as store:
        for expected in fixture_suites(name):
            loaded = store.load(expected.suite_id)
            assert loaded == expected and loaded.tools is None                # unknown, never invented
    assert user_version(path) == SCHEMA_VERSION == 3


def test_v2_fixture_keeps_its_recorded_retries(tmp_path):
    path = load_fixture_db(tmp_path / "v2.db", "results_v2")
    retried = fixture_suites("results_v2")[1]
    with ResultStore(path) as store:
        assert store.load(retried.suite_id).records[0].run.retries == retried.records[0].run.retries


def test_failed_v3_migration_rolls_back_to_version_2(tmp_path, monkeypatch):
    path = load_fixture_db(tmp_path / "v2.db", "results_v2")
    monkeypatch.setitem(storage.MIGRATIONS, 2, storage.MIGRATIONS[2] + "\nINSERT INTO no_such_table VALUES (1);")
    with pytest.raises(StorageError, match="nothing was changed"):
        ResultStore(path)
    assert user_version(path) == 2
    with sqlite3.connect(path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        columns = [c[1] for c in conn.execute("PRAGMA table_info(suite_runs)")]
    assert "tool_versions" not in tables and "tools_recorded" not in columns   # the ALTER was undone too


def test_fresh_and_upgraded_schemas_are_identical(tmp_path):
    def columns(path):
        with sqlite3.connect(path) as conn:
            return {t: conn.execute(f"PRAGMA table_info({t})").fetchall() for t in TABLES}   # allowlisted names
    ResultStore(tmp_path / "fresh.db").close()
    ResultStore(load_fixture_db(tmp_path / "v2.db", "results_v2")).close()
    assert columns(tmp_path / "fresh.db") == columns(tmp_path / "v2.db")


def test_comparing_an_old_stored_run_with_a_new_one_warns(careful, tmp_path):
    path = load_fixture_db(tmp_path / "v2.db", "results_v2")
    with ResultStore(path) as store:
        old = store.load(fixture_suites("results_v2")[0].suite_id)
    assert "tools were not recorded for" in compare([old, careful])

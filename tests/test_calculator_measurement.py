"""Step A.3 support: --tasks, the history TOOLS column, `measure`, and partial runs under a hard budget.

All agents here are SCRIPTED TEST FIXTURES (FakeLLM), never real models. Offline: no API calls.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.measurement import format_measurement, measure_task
from agentbench.models import AgentConfig
from agentbench.report import format_report
from agentbench.storage import ResultStore
from agentbench.suites import get_task, shop_registry
from agentbench.suites.shop_agents import CAREFUL, scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

ROOT = Path(__file__).resolve().parents[1]
SHOP_010 = [get_task("shop-010")]
FAKE_GEMINI = AgentConfig(name="gemini-default", provider="gemini", model="gemini-test", system_prompt="p")
ROUND_FAILS = LLMResponse(tool_request=ToolRequest(name="calculator",
                                                   arguments={"expression": "round(16107.32, 99)"}))   # digits > 10
QUOTA = LLMError("daily quota", kind="quota_exhausted", status_code=429)


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def careful_010(*extra):
    """The careful shop-010 script (4 requests), with extra steps inserted before the answer."""
    script = CAREFUL["shop-010"]
    return FakeLLM([*script[:-1], *extra, script[-1]])


def run(shop, make_llm, repeats, config=FAKE_GEMINI, **kwargs):
    return run_suite(SHOP_010, config, make_llm, shop_registry(shop), suite_name="shop", repeats=repeats,
                     progress=None, sleep=lambda s: None, **kwargs)


# ---------- partial runs under a hard budget (correction 2) ----------------------------------------

def total_requests(suite):
    return sum(r.run.llm_calls for r in suite.records)


def test_budget_cuts_the_third_repeat_and_says_so(shop):
    suite = run(shop, lambda t, r: careful_010(), repeats=3, request_budget=10, min_requests_to_start=1)
    assert total_requests(suite) == 10                                   # 4 + 4 + 2: never more than the cap
    assert [r.outcome for r in suite.records] == ["passed", "passed", "infra_error"]
    assert suite.records[2].run.error_kind == "budget_exhausted"
    report = format_report(suite)
    assert "INCOMPLETE" in report and "Stopped    : budget_exhausted in shop-010" in report
    assert "Pass rate  : 2/2" in report                                 # the cut run is NOT a wrong answer


def test_budget_too_low_to_start_skips_the_third_repeat(shop):
    suite = run(shop, lambda t, r: careful_010(), repeats=3, request_budget=10)   # needs ~5 to start
    assert [r.outcome for r in suite.records] == ["passed", "passed"] and len(suite.skipped) == 1
    assert total_requests(suite) == 8 and not suite.is_complete


# ---------- measure: grouped by agent AND tools; infra apart -----------------------------------------

@pytest.fixture
def store(shop, tmp_path):
    old = run(shop, lambda t, r: careful_010(ROUND_FAILS) if r == 0 else careful_010(), repeats=2)
    old = old.model_copy(update={"tools": None, "suite_id": "old00000"})       # stored before A.1: unknown
    new = run(shop, lambda t, r: FakeLLM([QUOTA]) if r == 1 else careful_010(), repeats=3,
              request_budget=30, min_requests_to_start=1)                         # repeat 2 hits the quota
    scripted = run(shop, scripted_agent("careful"), repeats=1, config=scripted_config("careful"))
    with ResultStore(tmp_path / "r.db") as s:
        for suite in (old, new, scripted):
            s.save(suite)
        yield s


def test_measure_never_mixes_agents(store):
    groups = measure_task(store, "shop-010")
    assert [(g.provider, g.tools == "unknown") for g in groups] == [("gemini", True), ("gemini", False), ("fake", False)]
    assert groups[1].calculator == "calculator v2" and groups[0].calculator == "unknown"


def test_measure_counts(store):
    old, new, scripted = measure_task(store, "shop-010")
    assert (old.passed, old.eligible, old.runs_with_round_errors, old.round_errors, old.tool_errors) == (2, 2, 1, 1, 1)
    assert old.llm_calls == [5, 4] and old.near_step_limit == 0 and old.step_limit_failures == 0
    # infra error and the skip after the circuit breaker are counted APART, not as wrong answers
    assert (new.passed, new.eligible, new.infra_errors, new.skipped, new.scheduled) == (1, 1, ["quota_exhausted"], 1, 3)
    assert new.llm_calls == [4]


def test_measure_output_states_its_limits(store):
    text = format_measurement("shop-010", measure_task(store, "shop-010"))
    assert "unknown (not recorded)" in text and "SCRIPTED scripted-careful-v1" in text
    assert "1 (quota_exhausted)" in text and "1/2 (1 errors)" in text
    assert "exploratory evidence, not statistical proof" in text
    assert "Infrastructure errors and skipped runs are excluded" in text


def test_measure_unknown_task(store):
    assert format_measurement("nope", measure_task(store, "nope")) == "No stored runs of 'nope'."


# ---------- history TOOLS column -------------------------------------------------------------------

def test_history_carries_the_tools_fingerprint(store):
    history = store.task_history("shop-010")
    unknown = [h for h in history if h.suite_id == "old00000"]
    assert unknown and all(h.tools_fingerprint is None and h.tools is None for h in unknown)
    recorded = [h for h in history if h.suite_id != "old00000"]
    assert all(h.tools_fingerprint and any(t.name == "calculator" and t.version == 2 for t in h.tools)
               for h in recorded)


def cli(*args):
    return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, capture_output=True, text=True,
                          timeout=60, encoding="utf-8")


def test_history_cli_shows_tools_and_unknown(store, tmp_path):
    out = cli(ROOT / "scripts" / "results.py", "--db", tmp_path / "r.db", "history", "shop-010").stdout
    assert "TOOLS" in out and "unknown" in out
    assert "= calculator v2, describe_table v1, list_tables v1, sql_query v1" in out


def test_measure_cli(store, tmp_path):
    out = cli(ROOT / "scripts" / "results.py", "--db", tmp_path / "r.db", "measure", "shop-010")
    assert out.returncode == 0 and "Exploratory before/after for shop-010" in out.stdout


# ---------- --tasks ----------------------------------------------------------------------------------

def test_tasks_flag_estimate_covers_only_the_chosen_task():
    out = cli(ROOT / "scripts" / "run_benchmark.py", "--agent", "gemini", "--tasks", "shop-010",
              "--repeats", "3", "--budget", "30")
    assert out.returncode == 0 and "Tasks      : shop-010" in out.stdout and "Runs       : 3" in out.stdout
    assert "72 worst case" in out.stdout and "Budget     : 30" in out.stdout   # 8 steps x 3 attempts x 3 runs
    assert "Nothing was sent" in out.stdout


@pytest.mark.parametrize("args, message", [
    (["--tasks", "shop-999"], "unknown task id(s) for suite shop: shop-999"),
    (["--suite", "shop-hard", "--tasks", "shop-010"], "unknown task id(s) for suite shop-hard: shop-010"),
    (["--suite", "nope"], "invalid choice: 'nope'"),
    (["--tasks", "shop-010", "shop-010"], "each task id may be given only once"),
])
def test_tasks_flag_validation(args, message):
    out = cli(ROOT / "scripts" / "run_benchmark.py", "--agent", "gemini", *args)
    assert out.returncode != 0 and message in out.stderr

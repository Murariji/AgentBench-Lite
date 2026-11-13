"""Step 8.3: failure section in the report, and `results.py failures`. Offline, stored traces only.

The "mixed" suite is a scripted TEST FIXTURE (careful agent, except two hand-written failures).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.report import export_json, format_failures, format_report
from agentbench.suites import SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

ROOT = Path(__file__).resolve().parents[1]
LOOP = LLMResponse(tool_request=ToolRequest(name="sql_query", arguments={"query": "SELECT COUNT(*) FROM orders"}))


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def run(shop, make_llm, **kwargs):
    return run_suite(SHOP_TASKS, scripted_config("careful"), make_llm, shop_registry(shop), suite_name="shop",
                     progress=None, sleep=lambda s: None, **kwargs)


@pytest.fixture(scope="module")
def careful(shop):
    return run(shop, scripted_agent("careful"))


@pytest.fixture(scope="module")
def mixed(shop):
    def make_llm(task, repeat):
        if task.id == "shop-001":
            return FakeLLM([LOOP] * 8)                         # stuck: same query until out of steps
        if task.id == "shop-002":
            return FakeLLM([LLMResponse(text="June")])         # right answer, but never queried: a guess
        return scripted_agent("careful")(task, repeat)
    return run(shop, make_llm)


@pytest.fixture(scope="module")
def stopped(shop):
    def make_llm(task, repeat):
        if task.id == "shop-003":
            return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
        return scripted_agent("careful")(task, repeat)
    return run(shop, make_llm, request_budget=80, min_requests_to_start=1)


# ---------- the report section --------------------------------------------------------------

def test_report_shows_categories_with_an_example(mixed):
    text = format_report(mixed)
    assert "Failure analysis (rule-based" in text and "Failed runs : 2 of 10 evaluated" in text
    assert "    no_data_used" in text and "    loop" in text
    assert "e.g. shop-001: the same call sql_query" in text
    assert text.index("no_data_used") < text.index("    loop")   # listed in priority order


def test_clean_run_says_so(careful):
    text = format_failures(careful)
    assert "Failed runs : 0 of 10 evaluated" in text and "Near misses : none" in text
    assert "Retries" not in text                                  # recorded (and none happened)


def test_infra_errors_are_reported_apart(stopped):
    text = format_failures(stopped)
    assert "Failed runs : 0 of 2 evaluated" in text               # quota is not an agent failure
    assert "Infra errors: 1 (not agent failures: quota_exhausted x1)" in text and "Skipped     : 7" in text


def test_detailed_view_lists_every_signal(mixed):
    text = format_failures(mixed, detailed=True)
    assert "shop-001     the same call" in text and "also: step_limit" in text and "also: no_final_answer" in text
    assert "shop-002     required tool(s) sql_query never called" in text


def test_unknown_retries_are_reported_as_unknown(careful):
    old = careful.model_copy(update={"records": [
        r.model_copy(update={"run": r.run.model_copy(update={"retries": None})}) for r in careful.records]})
    assert "not recorded for 10 run(s)" in format_failures(old) and "unknown, not zero" in format_failures(old)


def test_report_without_task_definitions(careful):
    assert "not available: this result has no task definitions" in format_report(careful.model_copy(update={"tasks": []}))


# ---------- the CLI over STORED runs -----------------------------------------------------------

def cli(*args, db):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "results.py"), "--db", str(db), *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=60, encoding="utf-8")


@pytest.fixture
def db(tmp_path, careful, mixed, stopped):
    path = tmp_path / "results.db"
    files = [str(export_json(s, tmp_path)) for s in (careful, mixed, stopped)]
    assert cli("import", *files, db=path).returncode == 0
    return path


def test_cli_failures_for_one_run(db, mixed):
    out = cli("failures", mixed.suite_id[:8], db=db)
    assert out.returncode == 0 and f"Suite {mixed.suite_id[:8]}" in out.stdout
    assert "loop" in out.stdout and "also: step_limit" in out.stdout


def test_cli_failures_across_all_runs(db):
    out = cli("failures", "--all", db=db).stdout
    assert "All 3 suite(s): 2 failed of 22 evaluated runs" in out   # 10 + 10 + 2 (quota run excluded)
    assert "no_data_used x1, loop x1" in out and "no failures" in out


def test_cli_failures_needs_an_id_or_all(db):
    assert cli("failures", db=db).returncode != 0
    assert cli("failures", "abc", "--all", db=db).returncode != 0

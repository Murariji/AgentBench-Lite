"""Step 8.2: failure analysis, tested with a FAILURE ZOO.

The zoo entries are SCRIPTED TEST FIXTURES, not intelligent agents: each FakeLLM script was
written by hand to produce one specific failure pattern. The tools, the shop database, the
AgentRunner and the evaluator are all REAL, so the traces look exactly like real runs.
Offline: no API calls.
"""

import json
from pathlib import Path

import pytest

from agentbench.analysis import DETECTORS, PRIORITY, analyze_run, analyze_suite, choose_primary
from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.evaluators import evaluate
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.models import AgentConfig, RunRecord, SuiteResult, is_infra_error
from agentbench.runner import AgentRunner
from agentbench.storage import ResultStore
from agentbench.suites import SHOP_TASKS, get_task, shop_registry
from agentbench.suites.shop_agents import scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

FIXTURES = Path(__file__).parent / "fixtures"
COUNT = "SELECT COUNT(*) FROM customers"          # shop-001: the correct query, returns 30


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


def tool(name, **arguments):
    return LLMResponse(tool_request=ToolRequest(name=name, arguments=arguments))


def sql(query):
    return tool("sql_query", query=query)


def answer(text):
    return LLMResponse(text=text)


def zoo(shop, task_id, script):
    """Run one scripted scenario through the REAL runner, tools, DB and evaluator; then analyse it."""
    task = get_task(task_id)
    run = AgentRunner(FakeLLM(script), shop_registry(shop), sleep=lambda s: None).run(task)
    if is_infra_error(run):
        record = RunRecord(task_id=task.id, repeat=0, run=run, outcome="infra_error")
    else:
        ev = evaluate(task, run)
        record = RunRecord(task_id=task.id, repeat=0, run=run, evaluation=ev,
                           outcome="passed" if ev.passed else "failed")
    return analyze_run(task, record), record


def names(signals):
    return {s.name for s in signals}


# ---------- the zoo: one primary category each ------------------------------------------

def test_guess_with_correct_answer_is_no_data_used(shop):
    a, record = zoo(shop, "shop-001", [answer("30")])
    checks = {c.name: c.passed for c in record.evaluation.checks}
    assert checks["answer:number"] and not checks["required_tools"]   # right answer, but a guess
    assert a.category == "no_data_used" and a.primary.tool_names == ["sql_query"]
    assert "never called" in a.primary.evidence and "without that data" in a.primary.evidence


def test_guess_with_wrong_answer_is_still_no_data_used(shop):
    a, _ = zoo(shop, "shop-001", [tool("list_tables"), answer("25")])
    assert a.category == "no_data_used"                                 # the root cause, not the wrong number


def test_invalid_tool_arguments_are_tool_misuse(shop):
    a, _ = zoo(shop, "shop-001", [tool("sql_query", sql=COUNT), answer("25")])   # "sql" is not a parameter
    assert a.category == "tool_misuse" and a.primary.step_indexes == [0]
    assert "bad arguments" in a.primary.evidence
    assert "unrecovered_tool_error" in names(a.additional_signals)      # symptom, kept as evidence


def test_tool_not_allowed_is_tool_misuse(shop):
    a, _ = zoo(shop, "shop-001", [tool("word_count", text="x"), sql("SELECT nope FROM t"), answer("25")])
    assert a.category == "tool_misuse" and "word_count" in a.primary.tool_names


def test_repeated_identical_query_is_a_loop(shop):
    variants = [COUNT, f"  {COUNT};", COUNT.replace(" ", "  ")] * 3    # whitespace/';' differences ignored
    a, _ = zoo(shop, "shop-001", [sql(q) for q in variants[:8]])
    assert a.category == "loop" and len(a.primary.step_indexes) == 8
    assert {"step_limit", "no_final_answer"} <= names(a.additional_signals)   # symptoms of the loop


def test_sql_error_without_recovery(shop):
    a, _ = zoo(shop, "shop-001", [sql("SELECT nope FROM customers"), answer("25")])
    assert a.category == "unrecovered_tool_error"
    assert "no such column: nope" in a.primary.evidence and a.primary.tool_names == ["sql_query"]


def test_sql_error_with_recovery_passes_with_a_warning(shop):
    a, record = zoo(shop, "shop-001", [sql("SELECT nope FROM customers"), sql(COUNT), answer("30")])
    assert record.outcome == "passed" and a.category is None and a.signals == []
    assert names(a.warnings) == {"recovered_tool_errors"} and a.warnings[0].step_indexes == [0]


def test_inner_join_trap_is_wrong_result(shop):
    inner = "SELECT COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"
    a, _ = zoo(shop, "shop-003", [sql(inner), answer("0")])
    assert a.category == "wrong_result" and a.primary.step_indexes == [0]
    assert "repeats the result of step 0" in a.primary.evidence


def test_correct_result_wrong_answer_is_misread(shop):
    a, _ = zoo(shop, "shop-001", [sql(COUNT), answer("35")])
    assert a.category == "misread_result" and "contained the correct value '30'" in a.primary.evidence


def test_misread_works_for_names_too(shop):
    query = ("SELECT p.name FROM products p WHERE p.id IN (SELECT product_id FROM order_items) "
             "ORDER BY p.price DESC LIMIT 1")
    a, _ = zoo(shop, "shop-004", [sql(query), answer("Smart Watch")])
    assert a.category == "misread_result"


def test_numeric_format_differences_are_handled(shop):
    a, _ = zoo(shop, "shop-006", [sql("SELECT 268721.0 AS total"), answer("₹2,68,722")])  # tool says 268721.0
    assert a.category == "misread_result"      # same value despite ".0", and the answer is read as 268722


def test_unparseable_answer(shop):
    a, _ = zoo(shop, "shop-001", [sql(COUNT), answer("thirty")])
    assert a.category == "unparseable_answer" and "no number found" in a.primary.evidence
    assert "misread_result" not in names(a.signals)    # can't call it a misread: the answer couldn't be read


def test_invalid_llm_response(shop):
    a, _ = zoo(shop, "shop-001", [LLMError("empty reply", kind="invalid_response")])
    assert a.category == "invalid_response"
    assert "no_data_used" in names(a.additional_signals)                # also true, lower priority


def test_step_limit_without_a_deeper_cause(shop):
    script = [tool("list_tables")] + [tool("describe_table", table=t)
                                      for t in ("customers", "orders", "products", "order_items")]
    script += [sql(COUNT), sql("SELECT COUNT(*) FROM orders"), sql("SELECT COUNT(*) FROM products")]
    a, _ = zoo(shop, "shop-001", script)
    assert a.category == "step_limit"
    assert names(a.signals) == {"step_limit", "no_final_answer"}


def test_unclassified_when_the_evidence_is_not_enough(shop):
    a, _ = zoo(shop, "shop-003", [sql(COUNT), answer("7")])   # 7 appears nowhere: not traceable
    assert a.category == "unclassified" and "answer:number" in a.primary.evidence


def test_large_outputs_never_count_as_misread(shop):
    a, _ = zoo(shop, "shop-001", [sql("SELECT id FROM customers"), answer("29")])   # 30 ids incl. "30"
    assert a.category != "misread_result"                    # 30 among 30 values may be chance


# ---------- priority, infra errors, passed runs ------------------------------------------------

def test_priority_is_centralized_and_ordered():
    assert tuple(DETECTORS) == PRIORITY
    assert choose_primary(["step_limit", "loop"]) == "loop"
    assert choose_primary(["wrong_result", "no_data_used"]) == "no_data_used"
    assert choose_primary([]) == "unclassified"


def test_unknown_tool_without_sql_is_no_data_used_with_misuse_as_signal(shop):
    a, _ = zoo(shop, "shop-001", [tool("run_python", code="1"), answer("25")])
    assert a.category == "no_data_used" and "tool_misuse" in names(a.additional_signals)


def test_infrastructure_errors_are_never_agent_failures(shop):
    a, record = zoo(shop, "shop-001", [LLMError("daily quota", kind="quota_exhausted", status_code=429)])
    assert record.outcome == "infra_error"
    assert a.category is None and a.signals == [] and a.warnings == []


def test_passed_run_near_the_step_limit(shop):
    script = [tool("list_tables")] + [tool("describe_table", table=t)
                                      for t in ("customers", "orders", "products", "order_items")]
    a, record = zoo(shop, "shop-001", script + [sql(COUNT), answer("30")])          # 7 of 8 steps
    assert record.outcome == "passed" and a.category is None
    assert a.warnings[0].name == "near_step_limit" and "7 of 8" in a.warnings[0].evidence


def test_retries_are_a_warning_not_a_failure(shop):
    busy = LLMError("busy", kind="server", status_code=503)
    a, record = zoo(shop, "shop-001", [busy, sql(COUNT), answer("30")])
    assert record.outcome == "passed" and a.retries_recorded
    assert names(a.warnings) == {"llm_retries"} and "server x1" in a.warnings[0].evidence


def test_ignored_tool_error_in_a_passed_run(shop):
    # sqrt() is not one of the calculator's allowed functions (round() is, since calculator v2)
    a, record = zoo(shop, "shop-001", [sql(COUNT), tool("calculator", expression="sqrt(900)"), answer("30")])
    assert record.outcome == "passed" and names(a.warnings) == {"unfixed_tool_errors"}


def test_old_runs_show_retries_as_unknown_not_zero(shop):
    _, record = zoo(shop, "shop-001", [sql(COUNT), answer("30")])
    old = record.model_copy(update={"run": record.run.model_copy(update={"retries": None, "llm_calls": 3})})
    a = analyze_run(get_task("shop-001"), old)
    assert not a.retries_recorded
    assert names(a.warnings) == {"unrecorded_retries_likely"} and "3 LLM calls for 2 steps" in a.warnings[0].evidence


def test_wrong_task_is_rejected(shop):
    _, record = zoo(shop, "shop-001", [sql(COUNT), answer("30")])
    with pytest.raises(ValueError):
        analyze_run(get_task("shop-002"), record)


# ---------- whole suites, and historical re-analysis ----------------------------------------------

def test_sloppy_agent_failures_are_all_wrong_results(shop):
    suite = run_suite(SHOP_TASKS, scripted_config("sloppy"), scripted_agent("sloppy"), shop_registry(shop),
                      suite_name="shop", progress=None)
    a = analyze_suite(suite)
    assert a.category_counts == {"wrong_result": 4} and (a.failed_runs, a.passed_runs) == (4, 6)
    assert [r.task_id for r in a.examples("wrong_result", limit=4)] == ["shop-003", "shop-004", "shop-007", "shop-009"]


def test_suite_with_infra_errors_and_skips(shop):
    def make_llm(task, repeat):
        if task.id == "shop-003":
            return FakeLLM([LLMError("daily quota", kind="quota_exhausted", status_code=429)])
        return scripted_agent("careful")(task, repeat)
    suite = run_suite(SHOP_TASKS, scripted_config("careful"), make_llm, shop_registry(shop), suite_name="shop",
                      progress=None, request_budget=80, min_requests_to_start=1)
    a = analyze_suite(suite)
    assert (a.infra_errors, a.skipped_runs, a.failed_runs, a.category_counts) == (1, 7, 0, {})


def test_suite_without_task_definitions_cannot_be_analysed(shop):
    suite = run_suite(SHOP_TASKS[:1], scripted_config("careful"), scripted_agent("careful"), shop_registry(shop),
                      suite_name="shop", progress=None)
    with pytest.raises(ValueError, match="no task definitions"):
        analyze_suite(suite.model_copy(update={"tasks": []}))


def test_historical_runs_are_reanalysed_from_storage(tmp_path):
    import sqlite3
    path = tmp_path / "v1.db"
    with sqlite3.connect(path) as conn:                      # the genuine schema-1 database from Step 8.1
        conn.executescript((FIXTURES / "results_v1.sql").read_text(encoding="utf-8"))
    expected = [SuiteResult.model_validate(s)
                for s in json.loads((FIXTURES / "results_v1_suites.json").read_text(encoding="utf-8"))]
    with ResultStore(path) as store:
        results = {s.config.name: analyze_suite(store.load(s.suite_id)) for s in expected}
    assert results["sloppy-script"].category_counts == {"wrong_result": 4}
    assert results["careful-script"].failed_runs == 0
    assert results["careful-script"].retries_not_recorded == 10        # unknown, never "0 retries"
    assert results["gemini-default"].infra_errors == 1 and results["gemini-default"].skipped_runs == 7

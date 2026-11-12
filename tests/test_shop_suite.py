"""Proves the Shop benchmark's answer key. "Who checks the checker?" - these tests do.

The reference SQL below is written INDEPENDENTLY of the task definitions (often with a
different approach: subqueries instead of JOINs, etc.), so one mistake can't hide in both.
"""

import calendar
import sqlite3
from pathlib import Path

import pytest

from agentbench.datasets import build_shop_db
from agentbench.evaluators import evaluate, extract_number
from agentbench.llm import FakeLLM, LLMResponse, ToolRequest
from agentbench.models import RunResult, Step, ToolCall, Trace
from agentbench.runner import AgentRunner
from agentbench.suites import SHOP_TASKS, SHOP_TOOLS, get_task, shop_registry
from agentbench.tools import ReadOnlySQLite


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    return build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")


@pytest.fixture(scope="module")
def conn(db_path):
    c = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    yield c
    c.close()


def rows(conn, sql):
    return conn.execute(sql).fetchall()


# ---------- reference answers: independent SQL, computed from the data -------

def ref_shop_001(conn):
    return str(rows(conn, "SELECT COUNT(*) FROM customers")[0][0])


def ref_shop_002(conn):
    ranked = rows(conn, """SELECT CAST(substr(order_date, 6, 2) AS INTEGER) AS m, COUNT(*) AS n
                           FROM orders WHERE order_date LIKE '2026-%' GROUP BY m ORDER BY n DESC""")
    return calendar.month_name[ranked[0][0]], ranked


def ref_shop_003(conn):
    return str(rows(conn, """SELECT COUNT(*) FROM customers
                             WHERE id NOT IN (SELECT customer_id FROM orders)""")[0][0])


def ref_shop_004(conn):
    ranked = rows(conn, """SELECT name, price FROM products
                           WHERE EXISTS (SELECT 1 FROM order_items WHERE product_id = products.id)
                           ORDER BY price DESC""")
    return ranked[0][0], [(r[0], r[1]) for r in ranked]


def ref_shop_005(conn):
    ranked = rows(conn, """SELECT (SELECT city FROM customers WHERE id = o.customer_id) AS city, COUNT(*) AS n
                           FROM orders o GROUP BY city ORDER BY n DESC""")
    return ranked[0][0], ranked


def _revenue_by(conn, group_sql):
    return rows(conn, f"""SELECT {group_sql} AS k,
                                 SUM(oi.quantity * (SELECT price FROM products WHERE id = oi.product_id)) AS r
                          FROM order_items oi GROUP BY k ORDER BY r DESC""")


def ref_shop_006(conn):
    return str(rows(conn, """SELECT SUM(oi.quantity * p.price)
                             FROM orders o, order_items oi, products p
                             WHERE oi.order_id = o.id AND p.id = oi.product_id
                               AND o.order_date BETWEEN '2026-01-01' AND '2026-01-31'""")[0][0])


def ref_shop_007(conn):
    ranked = _revenue_by(conn, "(SELECT name FROM products WHERE id = oi.product_id)")
    return ranked[0][0], ranked


def ref_shop_008(conn):
    ranked = _revenue_by(conn, """(SELECT c.name FROM orders o JOIN customers c ON c.id = o.customer_id
                                    WHERE o.id = oi.order_id)""")
    return ranked[0][0], ranked


def ref_shop_009(conn):
    jan = rows(conn, "SELECT COUNT(*) FROM orders WHERE order_date LIKE '2026-01-%'")[0][0]
    feb = rows(conn, "SELECT COUNT(*) FROM orders WHERE order_date LIKE '2026-02-%'")[0][0]
    return f"{(feb - jan) / jan * 100:.2f}"   # 23.81 - deliberately NOT pre-rounded to 23.8


def ref_shop_010(conn):
    total = rows(conn, """SELECT SUM(quantity * (SELECT price FROM products WHERE id = product_id))
                          FROM order_items""")[0][0]
    orders = rows(conn, "SELECT COUNT(*) FROM orders")[0][0]
    return f"{total / orders:.2f}"            # 16107.32


def reference_answer(task_id, conn) -> str:
    value = globals()[f"ref_{task_id.replace('-', '_')}"](conn)
    return value[0] if isinstance(value, tuple) else value


# ---------- 1. reference SQL agrees with the answer key ----------------------

@pytest.mark.parametrize("task", SHOP_TASKS, ids=lambda t: t.id)
def test_reference_sql_agrees_with_expected_answer(task, conn):
    reference = reference_answer(task.id, conn)
    if task.answer_type == "number":
        diff = abs(extract_number(reference).value - extract_number(task.expected_answer).value)
        assert float(diff) <= max(task.abs_tolerance, task.rel_tolerance * float(task.expected_answer))
    else:
        assert reference == task.expected_answer


# ---------- 2. "which X has the most" tasks have NO ties ---------------------

@pytest.mark.parametrize("ref", [ref_shop_002, ref_shop_004, ref_shop_005, ref_shop_007, ref_shop_008],
                         ids=["shop-002", "shop-004", "shop-005", "shop-007", "shop-008"])
def test_top_answers_are_unique(ref, conn):
    _, ranked = ref(conn)
    assert ranked[0][1] > ranked[1][1], f"tie at the top: {ranked[:2]}"


# ---------- 3. the evaluator accepts the correct answer, rejects the traps ---

def fake_result(task, answer: str) -> RunResult:
    """A hand-made run that used sql_query successfully and answered `answer`."""
    query = Step(index=0, llm_output="", tool_call=ToolCall(
        tool_name="sql_query", arguments={"query": "SELECT ..."}, output="..."))
    final = Step(index=1, llm_output=answer)
    return RunResult(task_id=task.id, status="completed", final_answer=answer,
                     trace=Trace(task_id=task.id, steps=[query, final]), duration_seconds=0.1)


@pytest.mark.parametrize("task", SHOP_TASKS, ids=lambda t: t.id)
def test_evaluator_accepts_the_reference_answer(task, conn):
    evaluation = evaluate(task, fake_result(task, reference_answer(task.id, conn)))
    assert evaluation.passed, [c.reason for c in evaluation.checks]


@pytest.mark.parametrize(
    "task_id, trap_answer",
    [
        ("shop-003", "0"),                    # INNER JOIN instead of LEFT JOIN
        ("shop-004", "Smart Watch"),          # most expensive overall, but never ordered
        ("shop-005", "Kolkata"),              # top city by CUSTOMERS (a tie!), not by orders
        ("shop-007", "Denim Jeans"),          # most UNITS sold, not most revenue
        ("shop-009", "24"),                   # rounded too far
        ("shop-009", "-19.2"),                # (jan - feb) / feb: wrong direction
        ("shop-010", "16100"),
    ],
)
def test_evaluator_rejects_trap_answers(task_id, trap_answer):
    task = get_task(task_id)
    assert not evaluate(task, fake_result(task, trap_answer)).passed


# ---------- 4-6. suite configuration is consistent ---------------------------

def test_task_ids_are_unique_and_there_are_ten():
    ids = [t.id for t in SHOP_TASKS]
    assert len(ids) == 10 and len(set(ids)) == 10


def test_tool_configuration(db_path):
    with ReadOnlySQLite(db_path) as db:
        registered = shop_registry(db).names()
    for task in SHOP_TASKS:
        assert task.allowed_tools == SHOP_TOOLS
        assert set(task.required_tools) <= set(task.allowed_tools)   # required ⊆ allowed
        assert set(task.allowed_tools) <= set(registered)            # nothing advertised that doesn't exist
        assert task.max_steps == 8


def test_answer_type_and_tolerance_configuration():
    for task in SHOP_TASKS:
        assert task.expected_answer
        if task.answer_type == "number":
            assert extract_number(task.expected_answer).value is not None
        else:
            assert task.abs_tolerance == 0 and task.rel_tolerance == 0   # tolerances only for numbers
    assert get_task("shop-009").abs_tolerance == 0.05
    assert get_task("shop-010").abs_tolerance == 1.0


def test_unknown_task_id_is_a_clear_error():
    with pytest.raises(KeyError):
        get_task("shop-999")


# ---------- end to end: real tools + real DB, scripted "model" ---------------

def scripted(*queries_then_answer):
    *queries, answer = queries_then_answer
    script = [LLMResponse(tool_request=ToolRequest(name="list_tables"))]
    script += [LLMResponse(tool_request=ToolRequest(name="sql_query", arguments={"query": q})) for q in queries]
    return FakeLLM(script + [LLMResponse(text=answer)])


def test_good_agent_passes_and_inner_join_mistake_fails(db_path):
    task = get_task("shop-003")
    good_sql = "SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"
    bad_sql = "SELECT COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"
    with ReadOnlySQLite(db_path) as db:
        good = AgentRunner(scripted(good_sql, "3"), shop_registry(db)).run(task)
        bad = AgentRunner(scripted(bad_sql, "0"), shop_registry(db)).run(task)
    assert good.trace.steps[1].tool_call.output.splitlines()[1] == "3"   # the REAL database said 3
    assert bad.trace.steps[1].tool_call.output.splitlines()[1] == "0"    # the REAL database said 0
    assert evaluate(task, good).passed
    bad_eval = evaluate(task, bad)
    assert bad.status == "completed" and not bad_eval.passed             # completed != correct
    assert [c.name for c in bad_eval.checks if not c.passed] == ["answer:number"]

"""Tests for the read-only SQL tools: valid analysis works, attacks fail safely.

Every test uses a temporary database. No API calls.
"""

import hashlib
import time
from pathlib import Path

import pytest

from agentbench.datasets import build_shop_db
from agentbench.tools import ReadOnlySQLite, ToolError, ToolRegistry, sql_tools


@pytest.fixture
def db_path(tmp_path) -> Path:
    return build_shop_db(tmp_path / "shop.db")


@pytest.fixture
def db(db_path):
    with ReadOnlySQLite(db_path, time_limit=0.5) as conn:  # short limit keeps tests fast
        yield conn


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_lines(output: str) -> list[str]:
    """Rows only: drop the header line and the footer line."""
    return output.splitlines()[1:-1]


# ---------- positive tests: legitimate analytical SQL must work --------------

def test_list_and_describe_tables(db):
    tools = {t.name: t for t in sql_tools(db)}
    assert tools["list_tables"].run() == "customers, order_items, orders, products"
    assert "order_date TEXT" in tools["describe_table"].run(table="orders")
    with pytest.raises(ToolError, match="no such table"):
        tools["describe_table"].run(table="payments")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) AS n FROM customers",
        "select name, price from products where category = 'Books' order by price desc",
        "SELECT city, COUNT(*) AS customers FROM customers GROUP BY city ORDER BY customers DESC",
        """SELECT p.name, SUM(i.quantity * p.price) AS revenue
           FROM order_items i JOIN products p ON p.id = i.product_id
           GROUP BY p.id ORDER BY revenue DESC LIMIT 3""",
        """SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
           WHERE o.id IS NULL""",
        """WITH monthly AS (SELECT strftime('%m', order_date) AS month, COUNT(*) AS n
                            FROM orders GROUP BY month)
           SELECT month, n FROM monthly ORDER BY month""",
        "WITH RECURSIVE nums(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM nums WHERE x < 5) SELECT SUM(x) FROM nums",
        "SELECT ROUND(AVG(price), 2), MIN(price), MAX(price) FROM products",
        "-- a comment first\nSELECT COUNT(*) FROM orders",
        "/* block comment */ SELECT 1",
    ],
)
def test_valid_analytical_queries_are_allowed(db, sql):
    output = db.query(sql)
    assert "blocked" not in output and "error" not in output.lower()
    assert output.splitlines()[-1].startswith("(")  # footer like "(3 rows)"


def test_query_results_are_correct(db):
    assert db.query("SELECT COUNT(*) AS n FROM customers") == "n\n30\n(1 row)"
    assert data_lines(db.query("SELECT SUM(x) FROM (SELECT 1 AS x UNION ALL SELECT 2)")) == ["3"]


# ---------- layer I: friendly message for non-SELECT -------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "DROP TABLE customers",
        "UPDATE products SET price = 0",
        "INSERT INTO customers VALUES (99, 'X', 'Y', '2026-01-01')",
        "CREATE TABLE notes (t TEXT)",
        "ALTER TABLE products ADD COLUMN x",
        "ATTACH 'other.db' AS other",
        "PRAGMA query_only = OFF",
        "   ",
    ],
)
def test_non_select_gets_a_clear_error(db, db_path, sql):
    before = file_hash(db_path)
    with pytest.raises(ToolError, match="Only read-only SELECT"):
        db.query(sql)
    assert file_hash(db_path) == before


# ---------- engine layers: attacks blocked even when layer I is bypassed -----

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "DROP TABLE customers",
        "UPDATE products SET price = 0",
        "INSERT INTO customers VALUES (99, 'X', 'Y', '2026-01-01')",
        "CREATE TABLE notes (t TEXT)",
        "ALTER TABLE products ADD COLUMN x",
        "WITH x AS (SELECT 1) DELETE FROM orders",          # starts with WITH: passes layer I!
        "WITH x AS (SELECT 1) UPDATE products SET price = 0",
        "ATTACH 'other.db' AS other",
        "DETACH main",
        "PRAGMA query_only = OFF",
        "PRAGMA writable_schema = ON",
        "BEGIN",
        "VACUUM",
        "SELECT load_extension('evil')",
    ],
)
def test_engine_blocks_attacks_even_without_text_check(db, db_path, sql):
    before = file_hash(db_path)
    with pytest.raises(ToolError, match="blocked|rejected|SQL error"):
        db._run(sql)  # skips layer I on purpose: proves regex is NOT our security boundary
    assert file_hash(db_path) == before                  # database file byte-for-byte unchanged
    assert db.query("SELECT COUNT(*) FROM orders").splitlines()[1] == "150"


def test_with_delete_bypass_is_still_blocked_through_the_tool(db, db_path):
    before = file_hash(db_path)
    with pytest.raises(ToolError, match="blocked"):
        db.query("WITH x AS (SELECT 1) DELETE FROM orders")
    assert file_hash(db_path) == before


def test_multiple_statements_are_rejected(db, db_path):
    before = file_hash(db_path)
    with pytest.raises(ToolError, match="one statement"):
        db.query("SELECT 1; DROP TABLE orders")
    assert file_hash(db_path) == before
    assert "orders" in db.schema


def test_attach_is_denied_for_other_files(db, tmp_path):
    other = build_shop_db(tmp_path / "other.db")
    with pytest.raises(ToolError, match="blocked"):
        db._run(f"ATTACH '{other}' AS other")


# ---------- resource limits ---------------------------------------------------

def test_infinite_recursion_is_stopped_by_time_limit(db):
    start = time.monotonic()
    with pytest.raises(ToolError, match="stopped"):
        db.query("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c")
    assert time.monotonic() - start < 5  # approximate limit, but bounded


def test_huge_cross_join_is_stopped_by_time_limit(db):
    with pytest.raises(ToolError, match="stopped"):
        db.query("SELECT COUNT(*) FROM order_items a, order_items b, order_items c, order_items d")


def test_huge_values_are_refused_by_size_limit(db):
    with pytest.raises(ToolError, match="too large"):
        db.query("SELECT randomblob(10000000)")


def test_overlong_sql_is_refused(db):
    with pytest.raises(ToolError, match="too large|SQL error"):
        db.query("SELECT " + " + ".join(["1"] * 3000))


# ---------- output limits -----------------------------------------------------

def test_large_result_sets_are_cut_to_max_rows(db):
    output = db.query("SELECT * FROM order_items")
    assert len(data_lines(output)) == 50
    assert "more rows exist" in output.splitlines()[-1]


def test_long_cells_are_truncated(db):
    output = db.query("SELECT hex(zeroblob(600)) AS big")
    cell = data_lines(output)[0]
    assert len(cell) == 201 and cell.endswith("…")  # 200 characters + "…"


def test_total_output_is_capped(db_path):
    with ReadOnlySQLite(db_path, max_output_chars=300) as small:
        output = small.query("SELECT * FROM customers")
    assert len(output) <= 300
    assert output.endswith("output truncated at 300 characters")


def test_nulls_blobs_and_empty_results(db):
    assert data_lines(db.query("SELECT NULL AS x")) == ["NULL"]
    assert data_lines(db.query("SELECT zeroblob(4) AS b")) == ["<blob 4 bytes>"]
    assert db.query("SELECT name FROM customers WHERE city = 'Atlantis'").endswith("(0 rows)")


# ---------- setup and agent-facing behaviour ---------------------------------

def test_missing_database_file_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReadOnlySQLite(tmp_path / "missing.db")


def test_registry_turns_blocked_queries_into_tool_errors(db, db_path):
    registry = ToolRegistry(sql_tools(db))
    before = file_hash(db_path)
    call = registry.execute("sql_query", {"query": "WITH x AS (SELECT 1) DELETE FROM orders"})
    assert call.output is None and "blocked" in call.error   # the agent sees an error, nothing crashes
    ok = registry.execute("sql_query", {"query": "SELECT COUNT(*) FROM products"})
    assert ok.error is None and "15" in ok.output
    assert file_hash(db_path) == before

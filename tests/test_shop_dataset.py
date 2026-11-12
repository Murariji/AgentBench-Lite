"""Tests for the sample shop database: deterministic, safe to build, has the edge cases."""

import sqlite3
from pathlib import Path

import pytest

from agentbench.datasets import build_shop_db


def dump(path: Path) -> str:
    conn = sqlite3.connect(path)
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


def scalar(path: Path, sql: str):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def db_path(tmp_path) -> Path:
    return build_shop_db(tmp_path / "shop.db")


def test_tables_and_sizes(db_path):
    assert scalar(db_path, "SELECT COUNT(*) FROM customers") == 30
    assert scalar(db_path, "SELECT COUNT(*) FROM products") == 15
    assert scalar(db_path, "SELECT COUNT(*) FROM orders") == 150


def test_same_seed_gives_identical_database(tmp_path):
    a = build_shop_db(tmp_path / "a.db")
    b = build_shop_db(tmp_path / "b.db")
    assert dump(a) == dump(b)


def test_never_overwrites_by_accident(db_path):
    before = db_path.read_bytes()
    with pytest.raises(FileExistsError):
        build_shop_db(db_path)
    assert db_path.read_bytes() == before  # untouched


def test_explicit_rebuild_replaces_safely(db_path, tmp_path):
    before = dump(db_path)
    build_shop_db(db_path, overwrite=True)
    assert dump(db_path) == before                       # same seed -> same data
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "shop.db"]
    assert leftovers == []                               # no temp files left behind


# ---------- the edge cases (traps for agents) --------------------------------

def test_many_cities_and_categories(db_path):
    assert scalar(db_path, "SELECT COUNT(DISTINCT city) FROM customers") == 7
    assert scalar(db_path, "SELECT COUNT(DISTINCT category) FROM products") == 4


def test_orders_span_six_months(db_path):
    assert scalar(db_path, "SELECT COUNT(DISTINCT strftime('%m', order_date)) FROM orders") == 6
    assert scalar(db_path, "SELECT MIN(order_date) >= '2026-01-01' AND MAX(order_date) <= '2026-06-30' FROM orders") == 1


def test_some_orders_have_several_products(db_path):
    assert scalar(db_path, """
        SELECT COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*) >= 2)
    """) > 0


def test_customers_without_orders_exist(db_path):
    assert scalar(db_path, """
        SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL
    """) == 3


def test_products_never_ordered_exist(db_path):
    assert scalar(db_path, """
        SELECT COUNT(*) FROM products p LEFT JOIN order_items i ON i.product_id = p.id WHERE i.order_id IS NULL
    """) == 2

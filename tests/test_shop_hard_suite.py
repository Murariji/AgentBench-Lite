"""shop-hard (Step A.2): every expected answer PROVEN independently, every trap REJECTED.

The proofs deliberately avoid the scripted agent's SQL: raw rows are fetched with plain SELECTs
and every answer is recomputed in ordinary Python (statistics, sets, Counter, datetime, Fraction).
If a proof disagreed with SHOP_HARD_TASKS, the TASK would be wrong - not the model.

The careful/sloppy agents are SCRIPTED TEST FIXTURES: their results prove the framework works on
these tasks; they say nothing about any real model's reasoning. Offline: no API calls.
"""

import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import pytest

from agentbench.analysis import analyze_suite
from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.evaluators import evaluate
from agentbench.models import RunResult, Step, ToolCall, Trace
from agentbench.suites import SHOP_HARD_TASKS, SHOP_TASKS, SUITES, get_task, shop_registry
from agentbench.suites.shop_agents import HARD_SLOPPY_TRAPS, scripted_agent, scripted_config
from agentbench.suites.shop_hard import SHOP_HARD_TRAPS
from agentbench.tools import ReadOnlySQLite

EXPECTED = {"hard-001": "10995.5", "hard-002": "5", "hard-003": "70.0", "hard-004": "7.68", "hard-005": "56.3",
            "hard-006": "April", "hard-007": "Monday", "hard-008": "Bengaluru", "hard-009": "21"}


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    return build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")


@pytest.fixture(scope="module")
def raw(db_path):
    """Plain table contents - no joins, no aggregation in SQL."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        return {
            "customers": conn.execute("SELECT id, name, city FROM customers").fetchall(),
            "products": conn.execute("SELECT id, name, category, price FROM products").fetchall(),
            "orders": conn.execute("SELECT id, customer_id, order_date FROM orders").fetchall(),
            "items": conn.execute("SELECT order_id, product_id, quantity FROM order_items").fetchall(),
        }


@pytest.fixture(scope="module")
def order_values(raw):
    price = {pid: p for pid, _, _, p in raw["products"]}
    values = defaultdict(int)
    for order_id, product_id, quantity in raw["items"]:
        values[order_id] += quantity * price[product_id]
    return values


def half_up(value: Fraction, places: int) -> Decimal:
    return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)


# ---------- 1. independent proofs (plain Python) ------------------------------------------------

def test_hard_001_median_order_value(raw, order_values):
    assert len(raw["orders"]) == 150 and set(order_values) == {o for o, _, _ in raw["orders"]}  # every order counts
    values = sorted(order_values.values())
    assert statistics.median(values) == 10995.5 == (values[74] + values[75]) / 2
    assert values[74] != values[75]                       # so "one middle value" really is a wrong answer
    assert round(statistics.mean(values)) == 16107        # the mean trap differs


def test_hard_002_january_but_not_february(raw):
    jan = {c for _, c, d in raw["orders"] if d.startswith("2026-01")}
    feb = {c for _, c, d in raw["orders"] if d.startswith("2026-02")}
    assert len(jan - feb) == 5 and len(jan) == 15
    assert sum(1 for _, c, d in raw["orders"] if d.startswith("2026-01") and c not in feb) == 7   # orders trap


def test_hard_003_share_of_all_customers_with_5_plus_orders(raw):
    counts = Counter(c for _, c, _ in raw["orders"])
    all_customers = [cid for cid, _, _ in raw["customers"]]
    share = Fraction(sum(counts[c] >= 5 for c in all_customers), len(all_customers)) * 100
    assert share == 70 and half_up(share, 1) == Decimal("70.0")
    buyers = [c for c in all_customers if counts[c] > 0]
    assert half_up(Fraction(sum(counts[c] >= 5 for c in buyers), len(buyers)) * 100, 1) == Decimal("77.8")


def test_hard_004_units_per_order(raw):
    units = Fraction(sum(q for _, _, q in raw["items"]), len(raw["orders"]))
    assert units == Fraction(768, 100)                    # exactly 7.68, no rounding involved
    assert half_up(Fraction(sum(q for _, _, q in raw["items"]), len(raw["items"])), 2) == Decimal("3.12")


def test_hard_005_electronics_revenue_share(raw):
    category = {pid: c for pid, _, c, _ in raw["products"]}
    price = {pid: p for pid, _, _, p in raw["products"]}
    revenue = Counter()
    for _, product_id, quantity in raw["items"]:
        revenue[category[product_id]] += quantity * price[product_id]
    share = Fraction(revenue["Electronics"], sum(revenue.values())) * 100
    assert half_up(share, 1) == Decimal("56.3")
    assert abs(float(share) - 56.35) > 0.005 and abs(float(share) - 56.25) > 0.005   # not on a rounding edge


def test_hard_006_largest_monthly_decrease(raw):
    per_month = Counter(date.fromisoformat(d).month for _, _, d in raw["orders"])
    changes = {m: per_month[m] - per_month[m - 1] for m in range(2, 7)}
    assert changes == {2: 5, 3: 0, 4: -2, 5: -1, 6: 7}
    worst = min(changes.values())
    assert [m for m, c in changes.items() if c == worst] == [4]          # unique: the tie rule isn't needed
    assert min(per_month, key=per_month.get) == 1 and max(changes, key=changes.get) == 6   # traps differ


def test_hard_007_busiest_weekday(raw):
    per_day = Counter(date.fromisoformat(d).strftime("%A") for _, _, d in raw["orders"])  # Python's own calendar
    (top, n), (_, runner_up) = per_day.most_common(2)
    assert top == "Monday" and n > runner_up                           # strictly highest
    assert per_day["Sunday"] < n and per_day["Tuesday"] < n


def test_hard_008_city_with_most_customers_tie_rule(raw):
    per_city = Counter(city for _, _, city in raw["customers"])
    best = max(per_city.values())
    tied = sorted(c for c, n in per_city.items() if n == best)
    assert tied == ["Bengaluru", "Chennai", "Jaipur", "Kolkata"]      # the tie is real: the rule decides
    assert tied[0] == "Bengaluru"


def test_hard_009_distinct_customers_of_a_product(raw):
    product = next(pid for pid, name, _, _ in raw["products"] if name == "Noise-Cancelling Headphones")
    customer_of = {oid: c for oid, c, _ in raw["orders"]}
    lines = [(o, q) for o, p, q in raw["items"] if p == product]
    assert len({customer_of[o] for o, _ in lines}) == 21
    assert len(lines) == 28 and sum(q for _, q in lines) == 104       # the traps differ


def test_expected_answers_match_the_proofs():
    assert {t.id: t.expected_answer for t in SHOP_HARD_TASKS} == EXPECTED


# ---------- 2. evaluator: correct forms accepted, every trap rejected --------------------------

def fake_result(task, answer: str) -> RunResult:
    """A hand-made run that used sql_query successfully and answered `answer`."""
    query = Step(index=0, llm_output="", tool_call=ToolCall(
        tool_name="sql_query", arguments={"query": "SELECT ..."}, output="..."))
    return RunResult(task_id=task.id, status="completed", final_answer=answer,
                     trace=Trace(task_id=task.id, steps=[query, Step(index=1, llm_output=answer)]),
                     duration_seconds=0.1)


ACCEPTED = [
    ("hard-001", "10995.5"), ("hard-001", "₹10,995.50"), ("hard-001", "10995.50"),
    ("hard-002", "5"),
    ("hard-003", "70.0"), ("hard-003", "70"), ("hard-003", "70%"), ("hard-003", "70.0 %"),
    ("hard-004", "7.68"), ("hard-004", "7.680"),
    ("hard-005", "56.3"), ("hard-005", "56.3%"), ("hard-005", "56.34"),     # more precise is still right
    ("hard-006", "April"), ("hard-006", "April 2026"),
    ("hard-007", "Monday"), ("hard-008", "Bengaluru"), ("hard-009", "21"),
]
TRAPS = [
    ("hard-001", "16107"), ("hard-001", "16107.32"), ("hard-001", "10995"), ("hard-001", "10996"),
    ("hard-002", "15"), ("hard-002", "7"),
    ("hard-003", "77.8"), ("hard-003", "77.78"),
    ("hard-004", "3.12"), ("hard-004", "2.46"), ("hard-004", "7.7"),        # 7.7: not two decimal places
    ("hard-005", "29.7"), ("hard-005", "33.3"), ("hard-005", "56"), ("hard-005", "56.4"),
    ("hard-006", "January"), ("hard-006", "June"), ("hard-006", "May"),
    ("hard-007", "Sunday"), ("hard-007", "Tuesday"),
    ("hard-008", "Kolkata"), ("hard-008", "Jaipur"), ("hard-008", "Chennai"),
    ("hard-009", "28"), ("hard-009", "104"),
]


@pytest.mark.parametrize("task_id, answer", ACCEPTED)
def test_correct_forms_are_accepted(task_id, answer):
    task = get_task(task_id)
    evaluation = evaluate(task, fake_result(task, answer))
    assert evaluation.passed, [c.reason for c in evaluation.checks]


@pytest.mark.parametrize("task_id, answer", TRAPS)
def test_trap_answers_are_rejected(task_id, answer):
    task = get_task(task_id)
    assert not evaluate(task, fake_result(task, answer)).passed


def test_every_task_has_a_documented_and_tested_trap():
    assert set(SHOP_HARD_TRAPS) == set(EXPECTED) == {t for t, _ in TRAPS}


# ---------- 3. suite structure ------------------------------------------------------------------------

def test_structure(db_path):
    ids = [t.id for t in SHOP_HARD_TASKS]
    assert len(ids) == 9 and len(set(ids)) == 9
    assert not set(ids) & {t.id for t in SHOP_TASKS}                       # unique across suites
    with ReadOnlySQLite(db_path) as db:
        registered = set(shop_registry(db).names())
    for task in SHOP_HARD_TASKS:
        assert task.max_steps == 10 and task.difficulty == "hard"
        assert set(task.required_tools) <= set(task.allowed_tools) <= registered
        assert "answer" in task.prompt.lower()                              # the format is stated


def test_tolerances_match_the_requested_precision():
    tol = {t.id: t.abs_tolerance for t in SHOP_HARD_TASKS if t.answer_type == "number"}
    assert tol == {"hard-001": 0.0, "hard-002": 0.0, "hard-003": 0.05, "hard-004": 0.005,
                   "hard-005": 0.05, "hard-009": 0.0}
    assert all(t.rel_tolerance == 0.0 for t in SHOP_HARD_TASKS)


def test_original_shop_suite_is_untouched():
    assert [t.id for t in SHOP_TASKS] == [f"shop-{i:03d}" for i in range(1, 11)]
    assert all(t.max_steps == 8 for t in SHOP_TASKS) and SUITES["shop"] is SHOP_TASKS


# ---------- 4. scripted agents (fixtures, NOT evidence about any real model) -------------------------------

@pytest.fixture(scope="module")
def runs(db_path):
    with ReadOnlySQLite(db_path) as db:
        return {kind: run_suite(SHOP_HARD_TASKS, scripted_config(kind), scripted_agent(kind), shop_registry(db),
                                suite_name="shop-hard", progress=None)
                for kind in ("careful", "sloppy")}


def test_careful_agent_solves_all_nine(runs):
    assert [r.outcome for r in runs["careful"].records] == ["passed"] * 9


def test_sloppy_agent_fails_exactly_its_traps(runs):
    failed = [r.task_id for r in runs["sloppy"].records if r.outcome == "failed"]
    assert failed == HARD_SLOPPY_TRAPS
    assert {r.task_id for r in runs["sloppy"].records if r.outcome == "passed"} == {"hard-002", "hard-005", "hard-006"}


def test_analyzer_on_the_sloppy_traps(runs):
    categories = {r.task_id: r.category for r in analyze_suite(runs["sloppy"]).runs if r.category}
    assert categories == {"hard-001": "wrong_result", "hard-003": "wrong_result", "hard-004": "wrong_result",
                          "hard-009": "wrong_result",
                          # Honest limitation: a weekday-number mix-up and an ignored tie rule leave no
                          # trace the rules can attribute -> "unclassified", never a guess.
                          "hard-007": "unclassified", "hard-008": "unclassified"}

"""SCRIPTED shop agents for testing the benchmark framework. NOT real AI.

Each "agent" is a FakeLLM following a fixed script per task. The SQL it writes is run on
the REAL database by the REAL tools, but every decision (which tool, which query, the
final answer) was written by a human in advance. Their scores say nothing about any
model's intelligence; they only prove that suite runs, metrics, reports and comparisons work.

    careful  - solves all 10 tasks correctly                      -> 10/10
    sloppy   - falls into 4 realistic traps (shop-003, 004, 007, 009) -> 6/10
"""

from agentbench.llm import FakeLLM, LLMResponse, ToolRequest
from agentbench.models import AgentConfig, Task
from agentbench.runner import DEFAULT_SYSTEM_PROMPT

REVENUE_JOIN = "FROM order_items i JOIN products p ON p.id = i.product_id"


def _sql(query: str) -> LLMResponse:
    return LLMResponse(tool_request=ToolRequest(name="sql_query", arguments={"query": query}))


def _calc(expression: str) -> LLMResponse:
    return LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": expression}))


def _answer(text: str) -> LLMResponse:
    return LLMResponse(text=text)


CAREFUL: dict[str, list[LLMResponse]] = {
    "shop-001": [_sql("SELECT COUNT(*) FROM customers"), _answer("30")],
    "shop-002": [_sql("SELECT strftime('%m', order_date) AS m, COUNT(*) AS n FROM orders "
                      "GROUP BY m ORDER BY n DESC LIMIT 1"), _answer("June")],
    "shop-003": [_sql("SELECT COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
                      "WHERE o.id IS NULL"), _answer("3")],
    "shop-004": [_sql("SELECT p.name, p.price FROM products p WHERE p.id IN "
                      "(SELECT product_id FROM order_items) ORDER BY p.price DESC LIMIT 1"),
                 _answer("Noise-Cancelling Headphones")],
    "shop-005": [_sql("SELECT c.city, COUNT(*) AS n FROM orders o JOIN customers c ON c.id = o.customer_id "
                      "GROUP BY c.city ORDER BY n DESC LIMIT 1"), _answer("Jaipur")],
    "shop-006": [_sql(f"SELECT SUM(i.quantity * p.price) {REVENUE_JOIN} JOIN orders o ON o.id = i.order_id "
                      "WHERE o.order_date LIKE '2026-01-%'"), _answer("268721")],
    "shop-007": [_sql(f"SELECT p.name, SUM(i.quantity * p.price) AS revenue {REVENUE_JOIN} "
                      "GROUP BY p.id ORDER BY revenue DESC LIMIT 1"), _answer("Noise-Cancelling Headphones")],
    "shop-008": [_sql(f"SELECT c.name, SUM(i.quantity * p.price) AS spent {REVENUE_JOIN} "
                      "JOIN orders o ON o.id = i.order_id JOIN customers c ON c.id = o.customer_id "
                      "GROUP BY c.id ORDER BY spent DESC LIMIT 1"), _answer("Ananya Iyer")],
    "shop-009": [_sql("SELECT strftime('%m', order_date) AS m, COUNT(*) FROM orders "
                      "WHERE m IN ('01', '02') GROUP BY m"),
                 _calc("(26 - 21) / 21 * 100"), _answer("23.8")],
    "shop-010": [_sql(f"SELECT SUM(i.quantity * p.price) {REVENUE_JOIN}"),
                 _sql("SELECT COUNT(*) FROM orders"),
                 _calc("2416098 / 150"), _answer("16107")],
}

# Same as careful, except four classic mistakes:
SLOPPY: dict[str, list[LLMResponse]] = {
    **CAREFUL,
    # INNER JOIN drops the customers without orders -> 0
    "shop-003": [_sql("SELECT COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id "
                      "WHERE o.id IS NULL"), _answer("0")],
    # forgets "has been ordered" -> the never-ordered Smart Watch
    "shop-004": [_sql("SELECT name, price FROM products ORDER BY price DESC LIMIT 1"),
                 _answer("Smart Watch")],
    # sums UNITS instead of revenue -> Denim Jeans
    "shop-007": [_sql(f"SELECT p.name, SUM(i.quantity) AS units {REVENUE_JOIN} "
                      "GROUP BY p.id ORDER BY units DESC LIMIT 1"), _answer("Denim Jeans")],
    # growth in the wrong direction: (jan - feb) / feb
    "shop-009": [_sql("SELECT strftime('%m', order_date) AS m, COUNT(*) FROM orders "
                      "WHERE m IN ('01', '02') GROUP BY m"),
                 _calc("(21 - 26) / 26 * 100"), _answer("-19.2")],
}

# ---- shop-hard (Step A.2): same two agents, same rules - SCRIPTED test fixtures, NOT real AI ----
ORDER_VALUES = ("SELECT o.id, SUM(i.quantity * p.price) AS v FROM orders o "
                "JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id GROUP BY o.id")
CUSTOMER_ORDER_COUNTS = ("SELECT c.id, COUNT(o.id) AS n FROM customers c "
                         "LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id")
MONTHLY = "SELECT strftime('%m', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY m ORDER BY m"
WEEKDAYS = "SELECT strftime('%w', order_date) AS d, COUNT(*) AS n FROM orders GROUP BY d ORDER BY n DESC"
HEADPHONES = ("FROM order_items i JOIN orders o ON o.id = i.order_id JOIN products p ON p.id = i.product_id "
              "WHERE p.name = 'Noise-Cancelling Headphones'")

HARD_CAREFUL: dict[str, list[LLMResponse]] = {
    "hard-001": [_sql(f"SELECT v FROM ({ORDER_VALUES}) ORDER BY v LIMIT 2 OFFSET 74"),   # 75th and 76th of 150
                 _calc("(10995 + 10996) / 2"), _answer("10995.5")],
    "hard-002": [_sql("SELECT COUNT(*) FROM customers WHERE "
                      "id IN (SELECT customer_id FROM orders WHERE order_date LIKE '2026-01-%') AND "
                      "id NOT IN (SELECT customer_id FROM orders WHERE order_date LIKE '2026-02-%')"), _answer("5")],
    "hard-003": [_sql(f"SELECT ROUND(100.0 * SUM(n >= 5) / COUNT(*), 1) FROM ({CUSTOMER_ORDER_COUNTS})"),
                 _answer("70.0")],
    "hard-004": [_sql("SELECT ROUND(1.0 * (SELECT SUM(quantity) FROM order_items) / "
                      "(SELECT COUNT(*) FROM orders), 2)"), _answer("7.68")],
    "hard-005": [_sql("SELECT ROUND(100.0 * SUM(CASE WHEN p.category = 'Electronics' THEN i.quantity * p.price END) "
                      f"/ SUM(i.quantity * p.price), 1) {REVENUE_JOIN}"), _answer("56.3")],
    "hard-006": [_sql(MONTHLY), _answer("April")],                       # changes: +5, 0, -2, -1, +7
    "hard-007": [_sql(WEEKDAYS), _answer("Monday")],                     # %w: 0 = Sunday, so 1 = Monday
    "hard-008": [_sql("SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC, city ASC LIMIT 1"),
                 _answer("Bengaluru")],
    "hard-009": [_sql(f"SELECT COUNT(DISTINCT o.customer_id) {HEADPHONES}"), _answer("21")],
}

# Same as careful, except six deliberate trap mistakes (each documented in suites/shop_hard.py):
HARD_SLOPPY: dict[str, list[LLMResponse]] = {
    **HARD_CAREFUL,
    "hard-001": [_sql(f"SELECT AVG(v) FROM ({ORDER_VALUES})"), _answer("16107")],          # the MEAN, not the median
    "hard-003": [_sql("SELECT ROUND(100.0 * SUM(n >= 5) / COUNT(*), 1) FROM "              # non-buyers dropped
                      "(SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id)"), _answer("77.8")],
    "hard-004": [_sql("SELECT ROUND(AVG(quantity), 2) FROM order_items"), _answer("3.12")],  # per LINE, not per order
    "hard-007": [_sql(WEEKDAYS), _answer("Sunday")],                                       # reads %w=1 as Sunday
    "hard-008": [_sql("SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC"),
                 _answer("Kolkata")],                                                       # tie rule ignored
    "hard-009": [_sql(f"SELECT COUNT(*) {HEADPHONES}"), _answer("28")],                     # order lines, not customers
}
HARD_SLOPPY_TRAPS = ["hard-001", "hard-003", "hard-004", "hard-007", "hard-008", "hard-009"]

CAREFUL.update(HARD_CAREFUL)
SLOPPY.update(HARD_SLOPPY)

SCRIPTS = {"careful": CAREFUL, "sloppy": SLOPPY}


def scripted_config(kind: str) -> AgentConfig:
    if kind not in SCRIPTS:
        raise KeyError(f"unknown scripted agent {kind!r}; available: {list(SCRIPTS)}")
    return AgentConfig(name=f"{kind}-script", provider="fake", model=f"scripted-{kind}-v1",
                       system_prompt=DEFAULT_SYSTEM_PROMPT)


def scripted_agent(kind: str):
    """An LLM factory for run_suite: a fresh FakeLLM with this task's script, every run."""
    scripts = SCRIPTS[kind]

    def make_llm(task: Task, repeat: int) -> FakeLLM:
        if task.id not in scripts:
            raise KeyError(f"the {kind} script has no entry for {task.id!r}")
        return FakeLLM(scripts[task.id])

    return make_llm

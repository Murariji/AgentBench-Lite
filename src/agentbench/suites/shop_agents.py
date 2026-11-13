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

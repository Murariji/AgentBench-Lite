"""The Shop Data Analyst benchmark: 10 tasks over the fixed-seed shop database.

Every expected answer is PROVEN in tests/test_shop_suite.py by an independently written
reference SQL query, and every "which X has the most..." task is checked for ties.

Good-task rules used here:
  1. exactly one correct answer (no ties)
  2. impossible without the database (the data exists nowhere else -> no contamination)
  3. the answer format is stated in the question
  4. tests a real skill (COUNT, dates, LEFT JOIN, multi-table JOIN, SUM, percentages)
  5. realistic traps (never-ordered products, customers without orders, units vs revenue)
"""

from agentbench.models import Task
from agentbench.tools import CalculatorTool, ReadOnlySQLite, ToolRegistry, sql_tools

SHOP_TOOLS = ["list_tables", "describe_table", "sql_query", "calculator"]
REVENUE = "Revenue means quantity x product price."
NUMBER_ONLY = "Answer with the number only."
NAME_ONLY = "Answer with the exact name only, as stored in the database."


def _task(task_id: str, prompt: str, expected: str, answer_type: str, **grading) -> Task:
    return Task(
        id=task_id,
        prompt=prompt,
        expected_answer=expected,
        answer_type=answer_type,
        allowed_tools=SHOP_TOOLS,
        required_tools=["sql_query"],
        max_steps=8,
        **grading,
    )


SHOP_TASKS: list[Task] = [
    # ---- easy ----
    _task("shop-001", f"How many customers are there? {NUMBER_ONLY}", "30", "number"),
    _task("shop-002", "Which month of 2026 had the most orders? Answer with the month name only.",
          "June", "contains"),
    # ---- medium ----
    _task("shop-003", f"How many customers have never placed an order? {NUMBER_ONLY}", "3", "number"),
    _task("shop-004", f"Name the most expensive product that has been ordered at least once. {NAME_ONLY}",
          "Noise-Cancelling Headphones", "contains"),
    _task("shop-005", "Which city's customers placed the most orders? Answer with the city name only.",
          "Jaipur", "contains"),
    _task("shop-006", f"What was the total revenue, in rupees, from orders placed in January 2026? "
                      f"{REVENUE} {NUMBER_ONLY}", "268721", "number"),
    # ---- hard ----
    _task("shop-007", f"Which product earned the most total revenue? {REVENUE} {NAME_ONLY}",
          "Noise-Cancelling Headphones", "contains"),
    _task("shop-008", f"Which customer spent the most in total? {REVENUE} {NAME_ONLY}",
          "Ananya Iyer", "contains"),
    _task("shop-009", "What was the percentage growth in the number of orders from January 2026 to "
                      "February 2026? Answer with the percentage to one decimal place, number only.",
          "23.8", "number", abs_tolerance=0.05),
    _task("shop-010", f"What was the average order value across all orders, in rupees, rounded to the "
                      f"nearest rupee? {REVENUE} {NUMBER_ONLY}", "16107", "number", abs_tolerance=1.0),
]


def get_task(task_id: str) -> Task:
    for task in SHOP_TASKS:
        if task.id == task_id:
            return task
    raise KeyError(f"no shop task {task_id!r}; available: {[t.id for t in SHOP_TASKS]}")


def shop_registry(db: ReadOnlySQLite) -> ToolRegistry:
    """Exactly the tools the shop tasks advertise: 3 read-only SQL tools + the safe calculator."""
    return ToolRegistry(sql_tools(db) + [CalculatorTool()])

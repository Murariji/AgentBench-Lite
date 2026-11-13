"""shop-hard: 9 harder Data Analyst tasks over the SAME fixed-seed shop database (Step A.2).

Why: the 10 shop tasks are too easy for the model we test (40 of 40 real runs passed), so they
can't separate configurations. These are realistic business questions where a plausible-looking
query gives a WRONG answer (averaging at the wrong level, losing rows in a JOIN, SQLite's weekday
numbering, ties, a median without a MEDIAN function).

Hard, not ambiguous: every rule (precision, ties, what counts) is written INTO the question, and
each number task has its OWN tolerance matching the precision it asks for. Every expected answer
is proven in tests/test_shop_hard_suite.py by an independent computation (often plain Python), and
every listed trap answer is shown to be rejected.

PRE-REGISTERED: these definitions were fixed and committed BEFORE any real model run. A later
correction must be a NEW task version (the tasks fingerprint and task_versions record it), never
a silent edit. See SHOP_HARD_REGISTRATION and docs/learning/benchmark-v2-notes.md.
"""

from agentbench.models import Task
from agentbench.suites.shop import NAME_ONLY, SHOP_TOOLS

ORDER_VALUE = ("An order's value is the sum of quantity x product price over all items in that order "
               "(all 150 orders count).")


def _hard(task_id: str, prompt: str, expected: str, answer_type: str, trap: str, **grading) -> Task:
    # `trap` is documentation only (the mistake this task targets); it is not part of the Task.
    return Task(
        id=task_id,
        difficulty="hard",
        prompt=prompt,
        expected_answer=expected,
        answer_type=answer_type,
        allowed_tools=SHOP_TOOLS,
        required_tools=["sql_query"],
        max_steps=10,          # shop uses 8; harder questions legitimately need more queries
        **grading,
    )


SHOP_HARD_TASKS: list[Task] = [
    _hard("hard-001",
          f"What is the median order value in rupees? {ORDER_VALUE} With an even number of orders, the "
          "median is the average of the two middle values. Answer with the exact number only (it may end in .5).",
          "10995.5", "number", abs_tolerance=0.0,
          trap="the mean (16107) or only one middle value (10995); SQLite has no MEDIAN function"),
    _hard("hard-002",
          "How many customers placed at least one order in January 2026 but no order in February 2026? "
          "Count customers, not orders. Answer with the number only.",
          "5", "number", abs_tolerance=0.0,
          trap="forgetting 'but no order in February' (15) or counting orders (7)"),
    _hard("hard-003",
          "What percentage of ALL customers (including customers who never ordered) placed 5 or more orders? "
          "Answer with the percentage to one decimal place, number only.",
          "70.0", "number", abs_tolerance=0.05,
          trap="dropping the 3 customers without orders from the denominator (77.8)"),
    _hard("hard-004",
          "What is the average number of units per order? Units per order = the sum of quantity over all items "
          "of that order; average over all 150 orders. Answer to two decimal places, number only.",
          "7.68", "number", abs_tolerance=0.005,
          trap="average quantity per order LINE (3.12) or average number of lines per order (2.46)"),
    _hard("hard-005",
          "What percentage of total revenue came from the Electronics category? Revenue means quantity x "
          "product price; divide Electronics revenue by the revenue of all categories. Answer with the "
          "percentage to one decimal place, number only.",
          "56.3", "number", abs_tolerance=0.05,
          trap="the share of units sold (29.7) or of products (33.3)"),
    _hard("hard-006",
          "Compare the number of orders in each month from February to June 2026 with the month before it "
          "(change = this month's orders minus the previous month's orders). Which month had the largest "
          "decrease, i.e. the most negative change? If several months tie, give the earliest. "
          "Answer with the month name only.",
          "April", "contains",
          trap="the month with the fewest orders (January) or the largest increase (June)"),
    _hard("hard-007",
          "On which day of the week were the most orders placed? Answer with the full English weekday name "
          "only (for example Wednesday).",
          "Monday", "contains",
          trap="SQLite's strftime('%w') numbers Sunday as 0: misreading it gives Sunday or Tuesday"),
    _hard("hard-008",
          "Which city has the most customers? If several cities tie, give the one that comes first "
          f"alphabetically. {NAME_ONLY}",
          "Bengaluru", "contains",
          trap="4 cities tie at 5 customers: ignoring the tie rule (e.g. LIMIT 1) returns an arbitrary one"),
    _hard("hard-009",
          "How many different customers bought the product 'Noise-Cancelling Headphones' at least once? "
          "Answer with the number only.",
          "21", "number", abs_tolerance=0.0,
          trap="counting order lines / orders (28) or units (104) instead of distinct customers"),
]

# The documented trap of each task (kept next to the tasks, used by tests and docs).
SHOP_HARD_TRAPS: dict[str, str] = {
    "hard-001": "mean 16107 / one middle value 10995", "hard-002": "15 (no 'not') / 7 (orders)",
    "hard-003": "77.8 (denominator without non-buyers)", "hard-004": "3.12 (per line) / 2.46 (lines per order)",
    "hard-005": "29.7 (units) / 33.3 (products)", "hard-006": "January (fewest) / June (largest increase)",
    "hard-007": "Sunday / Tuesday (%w off by one)", "hard-008": "Kolkata / Jaipur / Chennai (tie ignored)",
    "hard-009": "28 (order lines) / 104 (units)",
}

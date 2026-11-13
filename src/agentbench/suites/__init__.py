"""Benchmark task suites. Both run on the same shop database and the same tools."""

from agentbench.models import Task
from agentbench.suites.shop import SHOP_TASKS, SHOP_TOOLS, shop_registry
from agentbench.suites.shop_hard import SHOP_HARD_ACCEPTED, SHOP_HARD_REJECTED, SHOP_HARD_TASKS

# Suite name -> its tasks, in order. The name is what --suite and SuiteResult.suite_name use.
SUITES: dict[str, list[Task]] = {"shop": SHOP_TASKS, "shop-hard": SHOP_HARD_TASKS}
# Known (accepted, rejected) answers per registered suite: the guard runs them through today's evaluator.
GRADING_PROBES: dict[str, tuple] = {"shop-hard": (SHOP_HARD_ACCEPTED, SHOP_HARD_REJECTED)}


def get_task(task_id: str) -> Task:
    """Find a task in any suite (task ids are unique across suites)."""
    for tasks in SUITES.values():
        for task in tasks:
            if task.id == task_id:
                return task
    raise KeyError(f"no task {task_id!r}; suites: {', '.join(SUITES)}")


__all__ = ["SHOP_TASKS", "SHOP_HARD_TASKS", "SHOP_TOOLS", "SUITES", "GRADING_PROBES", "get_task", "shop_registry"]

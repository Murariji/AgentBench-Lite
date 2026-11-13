"""Free-tier safety tests (Step 6.3): pacing, hard request budget, circuit breaker, --yes.

No internet, no quota, no real waiting: a fake clock moves forward only when we "sleep".
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentbench.benchmark import estimate_requests, run_suite
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.llm.pacing import Pacer, RateLimitedLLM, RequestBudget
from agentbench.models import AgentConfig, SuiteResult, Task
from agentbench.report import format_report
from agentbench.suites import SHOP_TASKS
from agentbench.tools import CalculatorTool, ToolRegistry

ROOT = Path(__file__).resolve().parents[1]
CONFIG = AgentConfig(name="paced", provider="fake", model="scripted-v1", system_prompt="be careful",
                     min_interval_seconds=6.0)
TASKS = [Task(id=f"t{i}", prompt=f"{i}+{i}?", expected_answer=str(2 * i), answer_type="number")
         for i in range(1, 11)]                                       # 10 tasks, like the shop suite


class FakeTime:
    """clock() returns fake time; sleep() records the pause and moves the clock forward."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def solve(task: Task) -> FakeLLM:
    """2 requests per task: one calculator call, then the answer."""
    return FakeLLM([
        LLMResponse(tool_request=ToolRequest(name="calculator", arguments={"expression": task.prompt[:-1]})),
        LLMResponse(text=task.expected_answer),
    ])


def run(make_llm, *, budget=None, min_start=1, config=CONFIG, fake=None):
    fake = fake or FakeTime()
    messages: list[str] = []
    result = run_suite(TASKS, config, make_llm, ToolRegistry([CalculatorTool()]), suite_name="math",
                       request_budget=budget, min_requests_to_start=min_start,
                       progress=messages.append, sleep=fake.sleep, clock=fake.clock)
    return result, messages


def total_requests(result: SuiteResult) -> int:
    return sum(r.run.llm_calls for r in result.records)


# ---------- Pacer --------------------------------------------------------------

def test_first_request_never_waits_then_the_gap_is_kept():
    fake = FakeTime()
    pacer = Pacer(6.0, sleep=fake.sleep, clock=fake.clock)
    pacer.wait()
    assert fake.sleeps == []                       # nothing to wait for yet
    fake.now += 2.0                                # the request took 2 s
    pacer.wait()
    assert fake.sleeps == [4.0]                    # only the missing 4 s
    fake.now += 10.0                               # a slow request: already > 6 s apart
    pacer.wait()
    assert fake.sleeps == [4.0] and pacer.total_waited == 4.0


def test_zero_interval_never_sleeps_and_negative_is_rejected():
    fake = FakeTime()
    pacer = Pacer(0.0, sleep=fake.sleep, clock=fake.clock)
    for _ in range(5):
        pacer.wait()
    assert fake.sleeps == []
    with pytest.raises(ValueError):
        Pacer(-1.0)


# ---------- RequestBudget + RateLimitedLLM -------------------------------------

def test_budget_refuses_before_the_inner_llm_is_called():
    inner = FakeLLM([LLMResponse(text="a"), LLMResponse(text="b")])
    llm = RateLimitedLLM(inner, Pacer(0.0), RequestBudget(1))
    assert llm.generate([], []).text == "a"
    with pytest.raises(LLMError) as caught:
        llm.generate([], [])
    assert caught.value.kind == "budget_exhausted" and not caught.value.retryable
    assert len(inner.calls) == 1 and inner.remaining == 1    # the 2nd request was never sent


def test_budget_must_allow_at_least_one_request():
    with pytest.raises(ValueError):
        RequestBudget(0)


def test_wrapper_keeps_the_inner_name_for_traces():
    assert RateLimitedLLM(FakeLLM([]), Pacer(0.0)).name == "fake"


# ---------- pacing inside a suite ------------------------------------------------

def test_suite_requests_are_spaced_across_tasks():
    fake = FakeTime()
    starts: list[float] = []

    class Recording(FakeLLM):
        def generate(self, messages, tools, system_prompt=None):
            starts.append(fake.now)
            return super().generate(messages, tools, system_prompt)

    result, _ = run(lambda task, r: Recording(solve(task)._responses), fake=fake)
    assert result.is_complete and len(starts) == 20             # 10 tasks x 2 requests
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert min(gaps) >= 6.0                                     # also between two tasks


# ---------- hard request cap ------------------------------------------------------

def test_budget_is_a_hard_cap_and_the_cut_task_is_not_an_agent_failure():
    result, messages = run(lambda task, r: solve(task), budget=5)
    assert total_requests(result) == 5                          # exactly the cap, never more
    assert [r.outcome for r in result.records] == ["passed", "passed", "infra_error"]
    cut = result.records[2]
    assert cut.run.error_kind == "budget_exhausted" and cut.run.llm_calls == 1  # refused one not counted
    assert "STOPPED BY REQUEST BUDGET" in messages[2]
    assert [s.task_id for s in result.skipped] == [f"t{i}" for i in range(4, 11)]
    assert not result.is_complete and result.stop_reason == "budget_exhausted in t3"


def test_a_task_is_not_started_when_the_budget_cannot_cover_a_typical_run():
    created: list[str] = []

    def make_llm(task, repeat):
        created.append(task.id)
        return solve(task)

    result, messages = run(make_llm, budget=4, min_start=5)
    assert created == [] and result.records == []               # nothing started, 0 requests
    assert len(result.skipped) == 10 and "request budget: 4 of 4 left" in result.stop_reason
    assert any(m.startswith("STOPPED:") for m in messages)


# ---------- circuit breaker ---------------------------------------------------------

@pytest.mark.parametrize("kind", ["quota_exhausted", "auth"])
def test_circuit_breaker_skips_the_rest_with_zero_further_calls(kind):
    created: list[str] = []

    def make_llm(task, repeat):
        created.append(task.id)
        if task.id == "t3":
            return FakeLLM([LLMError("stop", kind=kind, status_code=429 if kind != "auth" else 401)])
        return solve(task)

    result, messages = run(make_llm, budget=80)
    assert created == ["t1", "t2", "t3"]                        # tasks 4-10 never even built an LLM
    assert total_requests(result) == 2 + 2 + 1
    assert result.records[2].outcome == "infra_error"
    assert [s.task_id for s in result.skipped] == [f"t{i}" for i in range(4, 11)]
    assert all(s.reason == f"{kind} in t3" for s in result.skipped)
    report = format_report(result)
    assert "INCOMPLETE" in report and f"Stopped    : {kind} in t3" in report
    assert "Requests   : 5 actual | estimate 50 | budget 80" in report


def test_a_temporary_error_does_not_trip_the_breaker():
    def make_llm(task, repeat):
        if task.id == "t3":   # still busy after every retry: this run fails, the suite goes on
            return FakeLLM([LLMError("busy", kind="server", status_code=503)] * 3)
        return solve(task)

    result, _ = run(make_llm)
    assert len(result.records) == 10 and result.skipped == [] and result.stop_reason is None


def test_safety_fields_survive_json():
    result, _ = run(lambda task, r: solve(task), budget=5)
    restored = SuiteResult.model_validate_json(result.model_dump_json())
    assert restored == result and restored.request_budget == 5


# ---------- the estimate ---------------------------------------------------------------

def test_estimate_for_the_shop_suite():
    config = AgentConfig(name="g", provider="gemini", model="m", system_prompt="p",
                         max_attempts=3, min_interval_seconds=6.0)
    est = estimate_requests(SHOP_TASKS, config, budget=80)
    assert (est.runs, est.typical_requests, est.worst_case_requests) == (10, 50, 240)  # 10 x 8 x 3
    assert est.expected_requests == 50
    assert estimate_requests(SHOP_TASKS, config, repeats=3, budget=80).expected_requests == 80


def test_real_run_is_refused_without_yes():
    env = {**os.environ, "GEMINI_API_KEY": "not-a-real-key", "GOOGLE_API_KEY": "not-a-real-key"}
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_benchmark.py"), "--agent", "gemini"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0
    assert "about 50 typical" in done.stdout and "240 worst case" in done.stdout
    assert "Nothing was sent. Add --yes" in done.stderr + done.stdout
    assert "running shop suite" not in done.stdout                 # the suite never started

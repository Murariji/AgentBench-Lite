"""Metrics from HAND-MADE records with exact expected values. No agent, no LLM."""

import pytest

from agentbench.evaluators import evaluate
from agentbench.metrics import compute_metrics
from agentbench.models import AgentConfig, RunRecord, RunResult, SkippedRun, Step, SuiteResult, Task, ToolCall, Trace

CONFIG = AgentConfig(name="test", provider="fake", model="scripted", system_prompt="be careful")


def task(task_id: str, difficulty=None) -> Task:
    return Task(id=task_id, prompt="2+2?", expected_answer="4", answer_type="number", difficulty=difficulty)


def record(task_id, outcome, *, repeat=0, difficulty=None, steps=2, llm_calls=2, seconds=1.0,
           tokens=None, tool_error=False) -> RunRecord:
    """outcome: 'passed' (answers 4), 'failed' (answers 5) or an error kind like 'quota_exhausted'."""
    call = ToolCall(tool_name="calculator", arguments={},
                    **({"error": "boom"} if tool_error else {"output": "4"}))
    trace = [Step(index=i, llm_output="", tool_call=call,
                  input_tokens=tokens and tokens[0], output_tokens=tokens and tokens[1])
             for i in range(steps)]
    t = task(task_id, difficulty)
    if outcome in ("passed", "failed"):
        answer = "4" if outcome == "passed" else "5"
        run = RunResult(task_id=task_id, status="completed", final_answer=answer,
                        trace=Trace(task_id=task_id, steps=trace), duration_seconds=seconds, llm_calls=llm_calls)
        return RunRecord(task_id=task_id, repeat=repeat, difficulty=difficulty, run=run,
                         evaluation=evaluate(t, run), outcome=outcome)
    run = RunResult(task_id=task_id, status="error", error="infra", error_kind=outcome,
                    trace=Trace(task_id=task_id, steps=[]), duration_seconds=seconds, llm_calls=llm_calls)
    return RunRecord(task_id=task_id, repeat=repeat, difficulty=difficulty, run=run, outcome="infra_error")


def suite(records, task_ids, repeats=1, skipped=()) -> SuiteResult:
    return SuiteResult(suite_name="t", config=CONFIG, task_ids=task_ids, repeats=repeats,
                       records=records, skipped=list(skipped))


# ---------- the spec example: 10 scheduled, 7 eligible, 5 passed, 3 infra ----

def test_infra_errors_are_not_agent_failures():
    records = ([record(f"t{i}", "passed") for i in range(5)]
               + [record(f"t{i}", "failed") for i in (5, 6)]
               + [record(f"t{i}", kind) for i, kind in zip((7, 8, 9), ("quota_exhausted", "network", "auth"))])
    m = compute_metrics(suite(records, [f"t{i}" for i in range(10)]))
    assert (m.scheduled_runs, m.eligible_runs, m.passed_runs, m.failed_runs, m.infra_errors) == (10, 7, 5, 2, 3)
    assert str(m.pass_rate) == "5/7 (71.4%)"     # the denominator is always shown
    assert m.complete is False                    # never presented as a full-suite result


def test_complete_suite():
    m = compute_metrics(suite([record("a", "passed"), record("b", "failed")], ["a", "b"]))
    assert m.complete and str(m.pass_rate) == "1/2 (50.0%)"


def test_skipped_runs_make_the_suite_incomplete():
    s = suite([record("a", "passed")], ["a", "b"], skipped=[SkippedRun(task_id="b", repeat=0, reason="stopped")])
    m = compute_metrics(s)
    assert m.skipped_runs == 1 and not m.complete and str(m.pass_rate) == "1/1 (100.0%)"


def test_no_eligible_runs_has_no_rate():
    m = compute_metrics(suite([record("a", "quota_exhausted")], ["a"]))
    assert m.pass_rate.rate is None and str(m.pass_rate) == "0/0 (n/a)" and m.avg_steps is None


# ---------- averages, totals, tools, checks ------------------------------------

def test_exact_averages_and_totals():
    records = [
        record("a", "passed", steps=2, llm_calls=2, seconds=1.0, tokens=(100, 10)),
        record("b", "failed", steps=4, llm_calls=6, seconds=3.0, tokens=(200, 20), tool_error=True),
        record("c", "network", llm_calls=3, seconds=10.0),          # infra: only in totals
    ]
    m = compute_metrics(suite(records, ["a", "b", "c"]))
    assert m.avg_steps == 3.0                 # (2 + 4) / 2, eligible runs only
    assert m.avg_llm_calls == 4.0             # (2 + 6) / 2
    assert m.avg_input_tokens == 500.0        # a: 2 steps x 100 = 200; b: 4 x 200 = 800 -> mean 500
    assert m.avg_output_tokens == 50.0        # a: 20; b: 80
    assert m.avg_duration_seconds == 2.0
    assert m.total_llm_calls == 11            # 2 + 6 + 3: infra runs still used quota
    assert m.total_duration_seconds == 14.0
    assert (m.tool_calls, m.tool_errors) == (6, 4)


def test_tokens_are_none_when_provider_reports_none():
    m = compute_metrics(suite([record("a", "passed")], ["a"]))
    assert m.avg_input_tokens is None and m.avg_output_tokens is None


def test_most_failed_checks():
    m = compute_metrics(suite([record("a", "failed"), record("b", "failed"), record("c", "passed")], ["a", "b", "c"]))
    assert m.failed_checks == [("answer:number", 2)]


def test_pass_rate_by_difficulty():
    records = [record("e1", "passed", difficulty="easy"), record("e2", "passed", difficulty="easy"),
               record("m1", "failed", difficulty="medium"), record("h1", "passed", difficulty="hard"),
               record("h2", "failed", difficulty="hard"), record("h3", "auth", difficulty="hard"),
               record("x", "passed")]
    m = compute_metrics(suite(records, ["e1", "e2", "m1", "h1", "h2", "h3", "x"]))
    assert {k: str(v) for k, v in m.by_difficulty.items()} == {
        "easy": "2/2 (100.0%)", "medium": "0/1 (0.0%)", "hard": "1/2 (50.0%)", "unrated": "1/1 (100.0%)",
    }


# ---------- repeats: pass@k and pass^k ------------------------------------------

def test_pass_at_k_and_pass_pow_k():
    records = [
        record("A", "passed", repeat=0), record("A", "passed", repeat=1),    # always passes
        record("B", "passed", repeat=0), record("B", "failed", repeat=1),    # sometimes
        record("C", "failed", repeat=0), record("C", "failed", repeat=1),    # never
        record("D", "passed", repeat=0), record("D", "network", repeat=1),   # incomplete -> excluded
    ]
    m = compute_metrics(suite(records, ["A", "B", "C", "D"], repeats=2))
    assert m.k == 2
    assert str(m.pass_at_k) == "2/3 (66.7%)"    # A, B
    assert str(m.pass_pow_k) == "1/3 (33.3%)"   # only A is reliable
    assert str(m.pass_rate) == "4/7 (57.1%)"    # per RUN: A A B D pass, B C C fail


def test_no_pass_at_k_without_repeats():
    m = compute_metrics(suite([record("a", "passed")], ["a"]))
    assert m.pass_at_k is None and m.pass_pow_k is None


# ---------- the models protect consistency -------------------------------------

def test_record_outcome_must_agree_with_evaluation():
    good = record("a", "passed")
    with pytest.raises(ValueError):
        RunRecord(task_id="a", repeat=0, run=good.run, evaluation=good.evaluation, outcome="failed")
    with pytest.raises(ValueError):
        RunRecord(task_id="a", repeat=0, run=good.run, outcome="infra_error")   # not an infra error


def test_prompt_hash_is_computed_not_trusted():
    a = AgentConfig(name="a", provider="fake", model="m", system_prompt="be careful")
    b = AgentConfig(name="b", provider="fake", model="m", system_prompt="be careful", prompt_hash="fake")
    c = AgentConfig(name="c", provider="fake", model="m", system_prompt="be quick")
    assert a.prompt_hash == b.prompt_hash != c.prompt_hash
    assert a.is_scripted

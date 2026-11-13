"""Step A.4a: the registration guard, partial-run reporting, run records, budget incl. retries.

Offline: scripted FakeLLM fixtures only (NOT real models), temporary databases, no API calls.
"""

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

import agentbench.registration as registration
from agentbench.benchmark import run_suite
from agentbench.datasets import build_shop_db
from agentbench.llm import FakeLLM, LLMError, LLMResponse, ToolRequest
from agentbench.models import AgentConfig
from agentbench.registration import build_registration, check_suite, load_registration, write_registration
from agentbench.report import compare, format_report
from agentbench.suites import GRADING_PROBES, SHOP_HARD_TASKS, SHOP_TASKS, shop_registry
from agentbench.suites.shop_agents import CAREFUL, scripted_agent, scripted_config
from agentbench.tools import ReadOnlySQLite

ROOT = Path(__file__).resolve().parents[1]
DATASET = "shop.db sha256:62143ef0c309"            # what shop-hard v1 was registered with
PROBES = GRADING_PROBES["shop-hard"]
PILOT = [t for t in SHOP_HARD_TASKS if t.id in ("hard-001", "hard-007")]
FAKE_GEMINI = AgentConfig(name="gemini-default", provider="gemini", model="gemini-test", system_prompt="p")


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    with ReadOnlySQLite(build_shop_db(tmp_path_factory.mktemp("shop") / "shop.db")) as conn:
        yield conn


@pytest.fixture(scope="module")
def tools(shop):
    return shop_registry(shop).specs()


def edit(task_id, **update):
    return [t.model_copy(update=update) if t.id == task_id else t for t in SHOP_HARD_TASKS]


# ---------- the guard: what it accepts ------------------------------------------------------------

def test_full_suite_matches(tools):
    g = check_suite("shop-hard", SHOP_HARD_TASKS, tools, DATASET, grading=PROBES)
    assert g.status == "matches" and not g.blocks_real_runs and g.problems == [] and g.notes == []
    assert g.line().startswith("shop-hard v1 matches (suite 5f106feaff34")


def test_pilot_is_a_subset_never_a_full_result(tools):
    g = check_suite("shop-hard", PILOT, tools, DATASET, grading=PROBES)
    assert g.status == "subset" and not g.blocks_real_runs
    assert "SUBSET of shop-hard v1: 2 of 9 tasks" in g.line() and "NOT a full-suite result" in g.line()


def test_unregistered_suite_is_said_plainly(tools):
    g = check_suite("shop", SHOP_TASKS, tools, DATASET)
    assert g.status == "unregistered" and not g.blocks_real_runs and "not registered" in g.line()


# ---------- the guard: what it refuses (refinement 1: the complete configuration) -------------------------

@pytest.mark.parametrize("tasks, expected", [
    (edit("hard-001", expected_answer="10996"), "hard-001.expected_answer: '10995.5' -> '10996'"),
    (edit("hard-004", abs_tolerance=1.0), "hard-004.abs_tolerance: 0.005 -> 1.0"),
    (edit("hard-002", max_steps=8), "hard-002.max_steps: 10 -> 8"),
    (edit("hard-003", required_tools=[]), "hard-003.required_tools: ['sql_query'] -> []"),
    (edit("hard-005", allowed_tools=["sql_query"]), "hard-005.allowed_tools"),
    (edit("hard-006", prompt="Reworded."), "hard-006 definition changed"),
    (SHOP_HARD_TASKS[::-1], "registered order"),                        # suite order is part of it
])
def test_any_task_change_blocks_real_runs(tools, tasks, expected):
    g = check_suite("shop-hard", tasks, tools, DATASET, grading=PROBES)
    assert g.blocks_real_runs and any(expected in p for p in g.problems), g.problems


def test_edited_pilot_task_blocks_the_pilot(tools):
    pilot = [t.model_copy(update={"abs_tolerance": 5.0}) if t.id == "hard-001" else t for t in PILOT]
    g = check_suite("shop-hard", pilot, tools, DATASET, grading=PROBES)
    assert g.blocks_real_runs and "hard-001.abs_tolerance: 0.0 -> 5.0" in g.problems


def test_tools_and_dataset_changes_block(tools):
    newer = [t.model_copy(update={"version": t.version + 1}) if t.name == "calculator" else t for t in tools]
    assert check_suite("shop-hard", SHOP_HARD_TASKS, newer, DATASET).blocks_real_runs
    g = check_suite("shop-hard", SHOP_HARD_TASKS, tools, "shop.db sha256:000000000000")
    assert g.blocks_real_runs and "dataset shop.db sha256:62143ef0c309 -> shop.db sha256:000000000000" in g.problems


def test_an_evaluator_change_is_caught_by_the_grading_probes(tools, monkeypatch):
    class Lenient:                          # pretend someone made the evaluator accept everything
        passed = True
    monkeypatch.setattr(registration, "evaluate", lambda task, run: Lenient())
    g = check_suite("shop-hard", SHOP_HARD_TASKS, tools, DATASET, grading=PROBES)
    assert g.blocks_real_runs
    assert "evaluator: hard-001 answer '16107' is now accepted (registered: rejected)" in g.problems


def test_what_cannot_be_checked_is_said(tools):
    g = check_suite("shop-hard", SHOP_HARD_TASKS, None, None)
    assert g.status == "matches"                                  # tasks match ...
    assert g.notes == ["tools not recorded: not verified", "dataset not checked", "grading probes not run here"]


def test_not_a_subset(tools):
    other = [SHOP_TASKS[0]]
    assert check_suite("shop-hard", other, tools, DATASET).blocks_real_runs


def test_a_matching_older_version_wins_over_a_stale_newer_one(tools, tmp_path):
    v1 = load_registration("shop-hard", 1)
    write_registration(v1, tmp_path)
    stale = build_registration("shop-hard", 2, edit("hard-001", expected_answer="1"), tools, dataset=DATASET,
                               git_head=None, source_committed=None)
    write_registration(stale, tmp_path)
    g = check_suite("shop-hard", SHOP_HARD_TASKS, tools, DATASET, grading=PROBES, directory=tmp_path)
    assert g.status == "matches" and g.registration["version"] == 1


# ---------- reports: registration line, run record, partial runs (refinements 2 and 4) ---------------------

def run(shop, tasks, make_llm, config=FAKE_GEMINI, **kwargs):
    return run_suite(tasks, config, make_llm, shop_registry(shop), suite_name="shop-hard",
                     dataset=DATASET, progress=None, sleep=lambda s: None, **kwargs)


def test_report_states_registration_and_run_record(shop):
    full = run(shop, SHOP_HARD_TASKS, scripted_agent("careful"), config=scripted_config("careful"))
    text = format_report(full)
    assert "Registered : shop-hard v1 matches" in text
    assert ("Run record : provider fake | model id scripted-careful-v1 (as requested; the provider may update "
            "the model behind an id)") in text
    assert f"config {full.config.config_fingerprint}" in text and "tools c1af5a87019e" in text
    assert "tasks ca11f5077756" in text and f"dataset {DATASET}" in text


def test_partial_pilot_is_reported_as_partial(shop):
    # hard-001 finishes (3 requests); hard-007 (needs 2) gets 1 request, then the hard budget of 4 cuts it
    pilot = run(shop, PILOT, lambda t, r: FakeLLM(CAREFUL[t.id]), request_budget=4, min_requests_to_start=1)
    text = format_report(pilot)
    assert "Registered : SUBSET of shop-hard v1: 2 of 9 tasks" in text and "NOT a full-suite result" in text
    assert "Status     : INCOMPLETE" in text
    assert "Completed  : hard-001" in text and "Not done   : hard-007 (budget_exhausted)" in text
    assert "Pass rate  : 1/1" in text                       # the cut run is not counted as a wrong answer


def test_skipped_pilot_task_is_listed(shop):
    pilot = run(shop, PILOT, lambda t, r: FakeLLM(CAREFUL[t.id]), request_budget=5)   # needs ~5 to start
    assert "Not done   : hard-007 (skipped)" in format_report(pilot)


def test_config_fingerprint_ignores_the_name_only():
    a = AgentConfig(name="a", provider="gemini", model="m", system_prompt="p")
    assert a.config_fingerprint == a.model_copy(update={"name": "b"}).config_fingerprint
    assert a.config_fingerprint != AgentConfig(name="a", provider="gemini", model="m", system_prompt="q").config_fingerprint
    assert a.config_fingerprint != AgentConfig(name="a", provider="gemini", model="m2", system_prompt="p").config_fingerprint


# ---------- budget = actual requests INCLUDING retries (refinement 3) -----------------------------------

def test_budget_counts_every_retry(shop):
    busy = LLMError("busy", kind="server", status_code=503)
    sent = []

    class Counting(FakeLLM):
        def generate(self, messages, tools, system_prompt=None):
            sent.append(1)                                   # a request that really left the program
            return super().generate(messages, tools, system_prompt)

    script = [busy, busy, *CAREFUL["hard-001"]]               # 2 retries, then 3 good requests = 5
    pilot = run(shop, PILOT, lambda t, r: Counting(script if t.id == "hard-001" else CAREFUL[t.id]),
                request_budget=6, min_requests_to_start=1)
    assert len(sent) == 6 == sum(r.run.llm_calls for r in pilot.records)    # never more than the cap
    first = pilot.records[0]
    assert first.outcome == "passed" and len(first.run.retries) == 2 and first.run.llm_calls == 5
    assert pilot.records[1].run.error_kind == "budget_exhausted"          # 1 request left: cut, not wrong


# ---------- separate experiments on different days (refinement 5) ----------------------------------------

def test_compare_flags_runs_from_different_days(shop):
    a = run(shop, PILOT, lambda t, r: FakeLLM(CAREFUL[t.id]))
    b = a.model_copy(update={"suite_id": "later", "started_at": a.started_at + timedelta(days=1)})
    text = compare([a, b])
    assert "these runs are from different days" in text and "treat them as separate experiments" in text
    same_day = a.model_copy(update={"suite_id": "same"})
    assert "different days" not in compare([a, same_day])


# ---------- the script refuses a real run that differs from its registration ---------------------------------

def test_real_run_is_refused_when_the_suite_differs(tools, tmp_path):
    stale = build_registration("shop-hard", 1, edit("hard-001", expected_answer="10996"), tools,
                               dataset=None, git_head=None, source_committed=None)
    write_registration(stale, tmp_path)
    env = {**os.environ, "AGENTBENCH_REGISTRATIONS_DIR": str(tmp_path),
           "GEMINI_API_KEY": "not-a-real-key", "GOOGLE_API_KEY": "not-a-real-key"}
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_benchmark.py"), "--agent", "gemini",
                          "--suite", "shop-hard", "--budget", "100", "--yes"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert out.returncode == 1
    assert "REFUSED" in out.stdout and "Nothing was sent" in out.stdout
    assert "hard-001.expected_answer: '10996' -> '10995.5'" in out.stdout
    assert "running shop-hard suite with REAL" not in out.stdout                 # no client was ever created


def test_real_run_estimate_shows_the_registration():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_benchmark.py"), "--agent", "gemini",
                          "--suite", "shop-hard", "--tasks", "hard-001", "hard-007", "--budget", "25"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert out.returncode == 0 and "Nothing was sent" in out.stdout
    assert "Registered : SUBSET of shop-hard v1: 2 of 9 tasks" in out.stdout
    assert "Budget     : 25 (hard cap: never exceeded)" in out.stdout

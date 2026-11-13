"""Suite pre-registration: freeze WHAT a benchmark is before anyone runs a real model on it.

A registration record (JSON, committed to git) stores:
  * the tasks fingerprint, a hash per task, and every expected answer + grading setting
  * the tools (name -> version) and tools fingerprint the suite was registered with
  * a suite fingerprint = hash of (tasks fingerprint, tools fingerprint)
  * the dataset fingerprint, the time, and the git commit the registration was made on

Rules:
  * A registration file is never overwritten (opened with mode "x").
  * A test compares today's suite with its registration. Any difference fails the test, naming it.
    A deliberate change means a NEW registered version (e.g. shop-hard.v2.json), never an edit.
"""

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agentbench.evaluators import evaluate
from agentbench.models import (RunResult, Step, Task, ToolCall, ToolSpec, Trace, canonical_json,
                               tasks_fingerprint, tools_fingerprint)

REGISTRATION_FORMAT = "agentbench-suite-registration/1"
# The committed registrations. AGENTBENCH_REGISTRATIONS_DIR can point elsewhere (used by tests only).
REGISTRATIONS_DIR = Path(os.environ.get("AGENTBENCH_REGISTRATIONS_DIR") or Path(__file__).parent / "suites" / "registrations")
GRADING_FIELDS = ("expected_answer", "answer_type", "abs_tolerance", "rel_tolerance", "required_tools",
                  "allowed_tools", "max_steps")


def task_hash(task: Task) -> str:
    """Same formula as the results database's task versions (storage.task_hash)."""
    return hashlib.sha256(task.model_dump_json().encode("utf-8")).hexdigest()


def suite_fingerprint(tasks_fp: str, tools_fp: str) -> str:
    return hashlib.sha256(canonical_json({"tasks": tasks_fp, "tools": tools_fp}).encode("utf-8")).hexdigest()[:12]


def git_state(repo: Path, path: Path) -> tuple[str | None, bool | None]:
    """(HEAD commit, is `path` committed unchanged?) - (None, None) when git is not available."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                              check=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", str(path)], cwd=repo, capture_output=True,
                               text=True, check=True, timeout=10).stdout.strip()
        return head, not dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def build_registration(suite: str, version: int, tasks: list[Task], tools: list[ToolSpec], *,
                       dataset: str | None, git_head: str | None, source_committed: bool | None) -> dict:
    tasks_fp, tools_fp = tasks_fingerprint(tasks), tools_fingerprint(tools)
    return {
        "format": REGISTRATION_FORMAT,
        "suite": suite,
        "version": version,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head,                     # the commit the registration was made on
        "suite_source_committed": source_committed,   # False = the task file was not yet committed then
        "suite_fingerprint": suite_fingerprint(tasks_fp, tools_fp),
        "tasks_fingerprint": tasks_fp,
        "tools_fingerprint": tools_fp,
        "tools": {t.name: t.version for t in tools},
        "dataset": dataset,
        "evaluation": "agentbench.evaluators.evaluate (deterministic checks: status, answer, required_tools)",
        "tasks": [{"id": t.id, "task_hash": task_hash(t), **{f: getattr(t, f) for f in GRADING_FIELDS}}
                  for t in tasks],
    }


def write_registration(record: dict, directory: Path = REGISTRATIONS_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['suite']}.v{record['version']}.json"
    with open(path, "x", encoding="utf-8") as f:     # "x": an existing registration is NEVER overwritten
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def load_registration(suite: str, version: int, directory: Path = REGISTRATIONS_DIR) -> dict:
    return json.loads((directory / f"{suite}.v{version}.json").read_text(encoding="utf-8"))


def differences(record: dict, tasks: list[Task], tools: list[ToolSpec]) -> list[str]:
    """Everything that differs between a registration and today's suite ([] = identical)."""
    problems = []
    if record["tasks_fingerprint"] != tasks_fingerprint(tasks):
        problems.append(f"tasks fingerprint {record['tasks_fingerprint']} -> {tasks_fingerprint(tasks)}")
    if record["tools_fingerprint"] != tools_fingerprint(tools):
        problems.append(f"tools fingerprint {record['tools_fingerprint']} -> {tools_fingerprint(tools)}")
    registered = {t["id"]: t for t in record["tasks"]}
    current = {t.id: t for t in tasks}
    for task_id in sorted(registered.keys() | current.keys()):
        if task_id not in current:
            problems.append(f"{task_id} removed")
        elif task_id not in registered:
            problems.append(f"{task_id} added")
        else:
            for f in GRADING_FIELDS:
                if registered[task_id][f] != getattr(current[task_id], f):
                    problems.append(f"{task_id}.{f}: {registered[task_id][f]!r} -> {getattr(current[task_id], f)!r}")
            if registered[task_id]["task_hash"] != task_hash(current[task_id]):
                problems.append(f"{task_id} definition changed (prompt or other fields)")
    return problems


# ---------- the registration guard (Step A.4a) ------------------------------------------------------

@dataclass
class GuardResult:
    """Is what is about to run (or what ran) exactly what was registered?"""

    suite: str
    status: str                      # "matches" | "subset" | "differs" | "unregistered"
    registration: dict | None = None
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)     # things that could not be checked
    selected: int = 0                                  # number of tasks checked

    @property
    def blocks_real_runs(self) -> bool:
        return self.status == "differs"

    def line(self) -> str:
        if self.status == "unregistered":
            return f"{self.suite}: not registered (no pre-registration exists for this suite)"
        r = self.registration
        where = f"suite {r['suite_fingerprint']}, registered at git {(r.get('git_head') or 'unknown')[:7]}"
        if self.status == "matches":
            text = f"{r['suite']} v{r['version']} matches ({where})"
        elif self.status == "subset":
            text = (f"SUBSET of {r['suite']} v{r['version']}: {self.selected} of {len(r['tasks'])} tasks, each "
                    f"matching its registered definition ({where}) - NOT a full-suite result")
        else:
            text = f"DIFFERS from {r['suite']} v{r['version']}: " + "; ".join(self.problems)
        return text + ("" if not self.notes else "  [" + "; ".join(self.notes) + "]")


def registrations_for(suite: str, directory: Path = REGISTRATIONS_DIR) -> list[dict]:
    """Every registered version of a suite, newest first."""
    records = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob(f"{suite}.v*.json")]
    return sorted((r for r in records if r.get("suite") == suite), key=lambda r: r["version"], reverse=True)


def probe_result(task: Task, answer: str) -> RunResult:
    """A hand-made run that used sql_query successfully and answered `answer` (for grading probes)."""
    query = Step(index=0, llm_output="", tool_call=ToolCall(tool_name="sql_query",
                                                             arguments={"query": "SELECT ..."}, output="..."))
    return RunResult(task_id=task.id, status="completed", final_answer=answer, duration_seconds=0.0,
                     trace=Trace(task_id=task.id, steps=[query, Step(index=1, llm_output=answer)]))


def grading_problems(tasks: list[Task], accepted: list[tuple[str, str]],
                     rejected: list[tuple[str, str]]) -> list[str]:
    """Run the known probe answers through TODAY's evaluator; list every verdict that changed."""
    by_id = {t.id: t for t in tasks}
    problems = []
    for expected_pass, probes in ((True, accepted), (False, rejected)):
        for task_id, answer in probes:
            if task_id not in by_id:
                continue
            passed = evaluate(by_id[task_id], probe_result(by_id[task_id], answer)).passed
            if passed != expected_pass:
                now, then = ("rejected", "accepted") if expected_pass else ("accepted", "rejected")
                problems.append(f"evaluator: {task_id} answer {answer!r} is now {now} (registered: {then})")
    return problems


def _compare(record: dict, tasks: list[Task], tools: list[ToolSpec] | None, dataset: str | None,
             grading: tuple | None) -> tuple[list[str], list[str], bool]:
    """(problems, notes, is_subset) of tasks / tools / dataset / grading against ONE registration."""
    registered_ids = [t["id"] for t in record["tasks"]]
    ids = [t.id for t in tasks]
    subset = ids != registered_ids
    problems, notes = [], []
    if subset:
        if not set(ids) <= set(registered_ids) or ids != [i for i in registered_ids if i in ids]:
            problems.append("tasks are not a subset of the registered tasks (in registered order)")
        else:
            registered = {t["id"]: t for t in record["tasks"]}
            for task in tasks:
                for f in GRADING_FIELDS:
                    if registered[task.id][f] != getattr(task, f):
                        problems.append(f"{task.id}.{f}: {registered[task.id][f]!r} -> {getattr(task, f)!r}")
                if registered[task.id]["task_hash"] != task_hash(task):
                    problems.append(f"{task.id} definition changed (prompt or other fields)")
    else:
        problems += [p for p in differences(record, tasks, tools or []) if not p.startswith("tools fingerprint")]
    if tools is None:
        notes.append("tools not recorded: not verified")
    elif tools_fingerprint(tools) != record["tools_fingerprint"]:
        problems.append(f"tools fingerprint {record['tools_fingerprint']} -> {tools_fingerprint(tools)}")
    if dataset is None:
        notes.append("dataset not checked")
    elif record.get("dataset") and dataset != record["dataset"]:
        problems.append(f"dataset {record['dataset']} -> {dataset}")
    if grading is None:
        notes.append("grading probes not run here")
    else:
        problems += grading_problems(tasks, *grading)
    return problems, notes, subset


def check_suite(suite: str, tasks: list[Task], tools: list[ToolSpec] | None, dataset: str | None, *,
                grading: tuple | None = None, directory: Path = REGISTRATIONS_DIR) -> GuardResult:
    """Compare tasks + tools + dataset (+ grading probes) with the suite's registrations.

    A registration that matches wins (newest first). If none matches, the result is "differs",
    reported against the newest registration. grading = (accepted, rejected) probe lists, or None.
    """
    records = registrations_for(suite, directory)
    if not records:
        return GuardResult(suite=suite, status="unregistered")
    for record in records:
        problems, notes, subset = _compare(record, tasks, tools, dataset, grading)
        if not problems:
            return GuardResult(suite=suite, status="subset" if subset else "matches", registration=record,
                               notes=notes, selected=len(tasks))
    problems, notes, _ = _compare(records[0], tasks, tools, dataset, grading)
    return GuardResult(suite=suite, status="differs", registration=records[0], problems=problems, notes=notes,
                       selected=len(tasks))

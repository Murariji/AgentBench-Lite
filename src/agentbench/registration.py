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
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agentbench.models import Task, ToolSpec, canonical_json, tasks_fingerprint, tools_fingerprint

REGISTRATION_FORMAT = "agentbench-suite-registration/1"
REGISTRATIONS_DIR = Path(__file__).parent / "suites" / "registrations"
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

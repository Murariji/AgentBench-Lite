"""ResultStore: the ONLY place that talks to the results database (repository pattern).

    store = ResultStore("data/results.db")
    suite_id = store.save(suite)        # one transaction: everything or nothing
    same = store.load(suite_id)         # an identical SuiteResult comes back

Tables (one-to-many, top to bottom):

    suite_runs ─┬─< suite_tasks >── task_versions   (immutable task snapshots, by content hash)
                ├─< run_records ─┬─< steps          (the trace; tool call columns are optional)
                │                └─< checks         (the evaluation; none for infra errors)
                └─< skipped_runs                    (runs that never happened, with the reason)

Rules: foreign keys ON for every connection, every value passed as a "?" parameter (never put
into SQL text), and a schema version in PRAGMA user_version. This file is separate from
shop.db: the agent's SQL tool can never see benchmark results or answers.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agentbench.models import (AgentConfig, Check, EvaluationResult, RunRecord, RunResult,
                               SkippedRun, Step, SuiteResult, Task, ToolCall, Trace)

DEFAULT_RESULTS_DB = Path("data") / "results.db"  # git-ignored (*.db)
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE suite_runs (
    suite_id             TEXT PRIMARY KEY,
    suite_name           TEXT NOT NULL,
    config_name          TEXT NOT NULL,
    provider             TEXT NOT NULL,
    model                TEXT NOT NULL,
    system_prompt        TEXT NOT NULL,
    prompt_hash          TEXT NOT NULL,
    max_attempts         INTEGER NOT NULL,
    min_interval_seconds REAL NOT NULL,
    repeats              INTEGER NOT NULL CHECK (repeats >= 1),
    started_at           TEXT NOT NULL,          -- ISO 8601, UTC
    finished_at          TEXT,
    dataset              TEXT,
    request_budget       INTEGER,
    estimated_requests   INTEGER,
    stop_reason          TEXT,
    saved_at             TEXT NOT NULL
);
CREATE INDEX idx_suite_runs_started ON suite_runs (started_at);

-- One row per DISTINCT task definition. task_hash = sha256 of the full definition, so an
-- edited prompt / answer / tolerance becomes a NEW row and old results keep their old version.
CREATE TABLE task_versions (
    task_hash       TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    definition_json TEXT NOT NULL
);
CREATE INDEX idx_task_versions_task ON task_versions (task_id);

-- Which tasks a suite run scheduled, in order, and exactly which version of each.
CREATE TABLE suite_tasks (
    suite_id  TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position  INTEGER NOT NULL,
    task_id   TEXT NOT NULL,
    task_hash TEXT REFERENCES task_versions (task_hash),  -- NULL = definition not recorded
    PRIMARY KEY (suite_id, position),
    UNIQUE (suite_id, task_id)
);

CREATE TABLE run_records (
    run_id            TEXT PRIMARY KEY,
    suite_id          TEXT NOT NULL,
    position          INTEGER NOT NULL,
    task_id           TEXT NOT NULL,
    repeat_index      INTEGER NOT NULL CHECK (repeat_index >= 0),
    difficulty        TEXT,
    outcome           TEXT NOT NULL CHECK (outcome IN ('passed', 'failed', 'infra_error')),
    status            TEXT NOT NULL,
    final_answer      TEXT,
    duration_seconds  REAL NOT NULL,
    error             TEXT,
    error_kind        TEXT,
    llm_calls         INTEGER NOT NULL,
    evaluation_passed INTEGER CHECK (evaluation_passed IN (0, 1)),  -- NULL = not evaluated
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id),
    UNIQUE (suite_id, position),
    UNIQUE (suite_id, task_id, repeat_index)
);
CREATE INDEX idx_run_records_task ON run_records (task_id);

CREATE TABLE steps (
    run_id              TEXT NOT NULL REFERENCES run_records (run_id),
    step_index          INTEGER NOT NULL CHECK (step_index >= 0),
    llm_output          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    tool_name           TEXT,                     -- NULL = this step called no tool
    tool_arguments_json TEXT,                     -- free-form arguments: JSON
    tool_output         TEXT,
    tool_error          TEXT,
    PRIMARY KEY (run_id, step_index),
    CHECK (tool_name IS NOT NULL
           OR (tool_arguments_json IS NULL AND tool_output IS NULL AND tool_error IS NULL))
);

CREATE TABLE checks (
    run_id   TEXT NOT NULL REFERENCES run_records (run_id),
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    passed   INTEGER NOT NULL CHECK (passed IN (0, 1)),
    reason   TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);

CREATE TABLE skipped_runs (
    suite_id     TEXT NOT NULL REFERENCES suite_runs (suite_id),
    position     INTEGER NOT NULL,
    task_id      TEXT NOT NULL,
    repeat_index INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    PRIMARY KEY (suite_id, position),
    FOREIGN KEY (suite_id, task_id) REFERENCES suite_tasks (suite_id, task_id)
);
"""

TABLES = ("suite_runs", "task_versions", "suite_tasks", "run_records", "steps", "checks", "skipped_runs")


class StorageError(Exception):
    """Saving or loading failed. The benchmark result itself is NOT affected by this."""


class DuplicateSuiteError(StorageError):
    pass


class SuiteNotFoundError(StorageError):
    pass


class SchemaVersionError(StorageError):
    pass


def task_hash(task: Task) -> str:
    return hashlib.sha256(task.model_dump_json().encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class ResultStore:
    def __init__(self, path: str | Path = DEFAULT_RESULTS_DB) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: WE decide where transactions begin and end (BEGIN / COMMIT).
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row            # rows readable by column name
        self._conn.execute("PRAGMA foreign_keys = ON")  # OFF by default in SQLite, per connection!
        self._prepare_schema()

    # ---------- lifecycle -------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _prepare_schema(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise SchemaVersionError(f"results database has schema version {version}; "
                                     f"this code understands version {SCHEMA_VERSION}")
        if self._conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]:
            raise SchemaVersionError("this file already contains tables but no AgentBench schema "
                                     "version - refusing to use it as a results database")
        # A brand-new file: create everything AND set the version in ONE transaction.
        # (PRAGMA cannot take "?" parameters; SCHEMA_VERSION is a constant from our code.)
        self._conn.executescript(f"BEGIN;\n{SCHEMA}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;")

    # ---------- save --------------------------------------------------------------

    def save(self, suite: SuiteResult) -> str:
        """Store a whole suite in ONE transaction. Returns its suite_id.

        On any failure everything written by this call is rolled back and StorageError is
        raised. The in-memory ``suite`` is untouched, so it can still be exported to JSON.
        """
        self._check_supported(suite)
        if self.exists(suite.suite_id):
            raise DuplicateSuiteError(f"suite {suite.suite_id} is already stored")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._insert_suite(suite)
            for position, record in enumerate(suite.records):
                self._insert_record(suite.suite_id, position, record)
            self._conn.executemany(
                "INSERT INTO skipped_runs (suite_id, position, task_id, repeat_index, reason) "
                "VALUES (?, ?, ?, ?, ?)",
                [(suite.suite_id, i, s.task_id, s.repeat, s.reason) for i, s in enumerate(suite.skipped)])
            self._conn.execute("COMMIT")
        except BaseException as exc:
            self._conn.execute("ROLLBACK")      # undo EVERYTHING from this save
            if isinstance(exc, sqlite3.IntegrityError):
                raise StorageError(f"rejected by a database rule, nothing saved: {exc}") from exc
            if isinstance(exc, sqlite3.Error):
                raise StorageError(f"database error, nothing saved: {exc}") from exc
            raise
        return suite.suite_id

    @staticmethod
    def _check_supported(suite: SuiteResult) -> None:
        # The schema stores task_id once per run; refuse data where nested copies disagree
        # instead of silently changing it on load.
        for record in suite.records:
            if record.run.trace.task_id != record.task_id:
                raise StorageError(f"run {record.run.run_id}: trace.task_id differs from task_id")
            if record.evaluation is not None and record.evaluation.task_id != record.task_id:
                raise StorageError(f"run {record.run.run_id}: evaluation.task_id differs from task_id")

    def _insert_suite(self, suite: SuiteResult) -> None:
        c = suite.config
        self._conn.execute(
            "INSERT INTO suite_runs (suite_id, suite_name, config_name, provider, model, system_prompt,"
            " prompt_hash, max_attempts, min_interval_seconds, repeats, started_at, finished_at, dataset,"
            " request_budget, estimated_requests, stop_reason, saved_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (suite.suite_id, suite.suite_name, c.name, c.provider, c.model, c.system_prompt,
             c.prompt_hash, c.max_attempts, c.min_interval_seconds, suite.repeats,
             _iso(suite.started_at), _iso(suite.finished_at), suite.dataset, suite.request_budget,
             suite.estimated_requests, suite.stop_reason, _iso(datetime.now(timezone.utc))))

        definitions = {t.id: t for t in suite.tasks}  # empty for results without task snapshots
        for position, task_id in enumerate(suite.task_ids):
            digest = None
            if task_id in definitions:
                digest = task_hash(definitions[task_id])
                self._conn.execute(  # same definition seen before -> already stored once
                    "INSERT INTO task_versions (task_hash, task_id, definition_json) VALUES (?, ?, ?)"
                    " ON CONFLICT (task_hash) DO NOTHING",
                    (digest, task_id, definitions[task_id].model_dump_json()))
            self._conn.execute(
                "INSERT INTO suite_tasks (suite_id, position, task_id, task_hash) VALUES (?, ?, ?, ?)",
                (suite.suite_id, position, task_id, digest))

    def _insert_record(self, suite_id: str, position: int, record: RunRecord) -> None:
        run, ev = record.run, record.evaluation
        self._conn.execute(
            "INSERT INTO run_records (run_id, suite_id, position, task_id, repeat_index, difficulty,"
            " outcome, status, final_answer, duration_seconds, error, error_kind, llm_calls,"
            " evaluation_passed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run.run_id, suite_id, position, record.task_id, record.repeat, record.difficulty,
             record.outcome, run.status, run.final_answer, run.duration_seconds, run.error,
             run.error_kind, run.llm_calls, None if ev is None else int(ev.passed)))
        self._conn.executemany(
            "INSERT INTO steps (run_id, step_index, llm_output, timestamp, input_tokens, output_tokens,"
            " tool_name, tool_arguments_json, tool_output, tool_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(run.run_id, s.index, s.llm_output, _iso(s.timestamp), s.input_tokens, s.output_tokens,
              *((s.tool_call.tool_name, json.dumps(s.tool_call.arguments, ensure_ascii=False),
                 s.tool_call.output, s.tool_call.error) if s.tool_call else (None, None, None, None)))
             for s in run.trace.steps])
        if ev is not None:
            self._conn.executemany(
                "INSERT INTO checks (run_id, position, name, passed, reason) VALUES (?, ?, ?, ?, ?)",
                [(run.run_id, i, ch.name, int(ch.passed), ch.reason) for i, ch in enumerate(ev.checks)])

    # ---------- load ----------------------------------------------------------------

    def exists(self, suite_id: str) -> bool:
        return self._conn.execute("SELECT 1 FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone() is not None

    def load(self, suite_id: str) -> SuiteResult:
        row = self._conn.execute("SELECT * FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone()
        if row is None:
            raise SuiteNotFoundError(f"no suite with id {suite_id!r}")
        config = AgentConfig(name=row["config_name"], provider=row["provider"], model=row["model"],
                             system_prompt=row["system_prompt"], max_attempts=row["max_attempts"],
                             min_interval_seconds=row["min_interval_seconds"])
        scheduled = self._conn.execute(
            "SELECT st.task_id, tv.definition_json FROM suite_tasks st"
            " LEFT JOIN task_versions tv ON tv.task_hash = st.task_hash"
            " WHERE st.suite_id = ? ORDER BY st.position", (suite_id,)).fetchall()
        tasks = [Task.model_validate_json(r["definition_json"]) for r in scheduled if r["definition_json"]]
        records = [self._load_record(r) for r in self._conn.execute(
            "SELECT * FROM run_records WHERE suite_id = ? ORDER BY position", (suite_id,))]
        skipped = [SkippedRun(task_id=r["task_id"], repeat=r["repeat_index"], reason=r["reason"])
                   for r in self._conn.execute(
                       "SELECT * FROM skipped_runs WHERE suite_id = ? ORDER BY position", (suite_id,))]
        # The SuiteResult validators run again here: loaded data is checked, not trusted.
        return SuiteResult(
            suite_id=row["suite_id"], suite_name=row["suite_name"], config=config,
            task_ids=[r["task_id"] for r in scheduled], repeats=row["repeats"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            records=records, skipped=skipped, tasks=tasks, dataset=row["dataset"],
            request_budget=row["request_budget"], estimated_requests=row["estimated_requests"],
            stop_reason=row["stop_reason"])

    def _load_record(self, row: sqlite3.Row) -> RunRecord:
        run_id = row["run_id"]
        steps = [Step(index=s["step_index"], llm_output=s["llm_output"], timestamp=s["timestamp"],
                      input_tokens=s["input_tokens"], output_tokens=s["output_tokens"],
                      tool_call=None if s["tool_name"] is None else ToolCall(
                          tool_name=s["tool_name"], arguments=json.loads(s["tool_arguments_json"]),
                          output=s["tool_output"], error=s["tool_error"]))
                 for s in self._conn.execute(
                     "SELECT * FROM steps WHERE run_id = ? ORDER BY step_index", (run_id,))]
        run = RunResult(run_id=run_id, task_id=row["task_id"], status=row["status"],
                        final_answer=row["final_answer"], trace=Trace(task_id=row["task_id"], steps=steps),
                        duration_seconds=row["duration_seconds"], error=row["error"],
                        error_kind=row["error_kind"], llm_calls=row["llm_calls"])
        evaluation = None
        if row["evaluation_passed"] is not None:
            checks = [Check(name=c["name"], passed=bool(c["passed"]), reason=c["reason"])
                      for c in self._conn.execute(
                          "SELECT * FROM checks WHERE run_id = ? ORDER BY position", (run_id,))]
            evaluation = EvaluationResult(run_id=run_id, task_id=row["task_id"],
                                          passed=bool(row["evaluation_passed"]), checks=checks)
        return RunRecord(task_id=row["task_id"], repeat=row["repeat_index"], difficulty=row["difficulty"],
                         run=run, evaluation=evaluation, outcome=row["outcome"])

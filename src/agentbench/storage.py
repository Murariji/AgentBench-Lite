"""ResultStore: the ONLY place that talks to the results database (repository pattern).

    store = ResultStore("data/results.db")
    suite_id = store.save(suite)        # one transaction: everything or nothing
    same = store.load(suite_id)         # an identical SuiteResult comes back

Tables (one-to-many, top to bottom):

    suite_runs ─┬─< suite_tasks >── task_versions   (immutable task snapshots, by content hash)
                ├─< run_records ─┬─< steps          (the trace; tool call columns are optional)
                │                └─< checks         (the evaluation; none for infra errors)
                │                └─< retries        (retried LLM requests; schema v2)
                ├─< skipped_runs                    (runs that never happened, with the reason)
                └─< suite_tools >── tool_versions   (tool snapshots by content hash; schema v3)

Rules: foreign keys ON for every connection, every value passed as a "?" parameter (never put
into SQL text), and a schema version in PRAGMA user_version. This file is separate from
shop.db: the agent's SQL tool can never see benchmark results or answers.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from agentbench.metrics import Rate
from agentbench.models import (AgentConfig, Check, EvaluationResult, RetryEvent, RunRecord, RunResult,
                               ToolSpec, canonical_json, tools_fingerprint,
                               SkippedRun, Step, SuiteResult, Task, ToolCall, Trace)
from agentbench.report import RESULTS_DIR, export_json

DEFAULT_RESULTS_DB = Path("data") / "results.db"  # git-ignored (*.db)
SCHEMA_VERSION = 3

# Version 1 (Phase 7). Never edit it: databases in the wild were created with it.
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

# Each migration upgrades version N to N+1. A NEW database also runs them, starting from SCHEMA
# (version 1): one path for everyone, so fresh and upgraded databases are always identical.
MIGRATIONS: dict[int, str] = {
    1: """
    -- Phase 8: record retried LLM requests.
    -- 0 for every EXISTING run: those runs never captured retries (unknown, NOT zero).
    ALTER TABLE run_records ADD COLUMN retries_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (retries_recorded IN (0, 1));
    CREATE TABLE retries (
        run_id         TEXT NOT NULL REFERENCES run_records (run_id),
        position       INTEGER NOT NULL,
        step_index     INTEGER NOT NULL CHECK (step_index >= 0),
        attempt        INTEGER NOT NULL CHECK (attempt >= 1),
        error_kind     TEXT NOT NULL,
        status_code    INTEGER,
        waited_seconds REAL NOT NULL CHECK (waited_seconds >= 0),
        request_id     TEXT,
        occurred_at    TEXT NOT NULL,
        succeeded      INTEGER NOT NULL CHECK (succeeded IN (0, 1)),
        PRIMARY KEY (run_id, position)
    );
    """,
    2: """
    -- Step A.1: which tool versions each suite run offered the agent.
    -- 0 for every EXISTING suite: its tools were never recorded (unknown, NOT assumed identical).
    ALTER TABLE suite_runs ADD COLUMN tools_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (tools_recorded IN (0, 1));
    -- One row per DISTINCT tool spec (name + version + description + parameters), keyed by the
    -- sha256 of its canonical JSON - stored once, however many suites used it.
    CREATE TABLE tool_versions (
        tool_hash TEXT PRIMARY KEY,
        name      TEXT NOT NULL,
        version   INTEGER NOT NULL CHECK (version >= 1),
        spec_json TEXT NOT NULL
    );
    CREATE INDEX idx_tool_versions_name ON tool_versions (name);
    CREATE TABLE suite_tools (
        suite_id  TEXT NOT NULL REFERENCES suite_runs (suite_id),
        position  INTEGER NOT NULL,
        tool_hash TEXT NOT NULL REFERENCES tool_versions (tool_hash),
        PRIMARY KEY (suite_id, position)
    );
    """,
}

TABLES = ("suite_runs", "task_versions", "suite_tasks", "run_records", "steps", "checks", "skipped_runs",
          "retries", "tool_versions", "suite_tools")


class StorageError(Exception):
    """Saving or loading failed. The benchmark result itself is NOT affected by this."""


class DuplicateSuiteError(StorageError):
    pass


class SuiteNotFoundError(StorageError):
    pass


class AmbiguousSuiteIdError(SuiteNotFoundError):
    """A short id matches more than one suite (a subclass, so existing callers still catch it)."""


class SchemaVersionError(StorageError):
    pass


class SuiteSummary(BaseModel):
    """One line of "all my benchmark runs". Counts come from SQL aggregation, not Python."""

    suite_id: str
    suite_name: str
    config_name: str
    provider: str
    model: str
    repeats: int
    started_at: datetime
    finished_at: datetime | None
    scheduled_runs: int
    passed: int
    failed: int
    infra_errors: int
    skipped: int
    total_llm_calls: int
    stop_reason: str | None

    @property
    def is_scripted(self) -> bool:
        return self.provider == "fake"

    @property
    def pass_rate(self) -> Rate:
        return Rate(passed=self.passed, eligible=self.passed + self.failed)

    @property
    def complete(self) -> bool:
        return (self.skipped == 0 and self.infra_errors == 0
                and self.passed + self.failed == self.scheduled_runs)


class TaskHistoryEntry(BaseModel):
    """One scheduled run of one task in one suite: executed (passed/failed/infra) or skipped."""

    suite_id: str
    started_at: datetime
    config_name: str
    provider: str
    model: str
    prompt_hash: str
    task_hash: str | None          # which VERSION of the task (None = definition not recorded)
    repeat: int
    outcome: str                   # passed | failed | infra_error | skipped
    error_kind: str | None = None
    llm_calls: int | None = None
    duration_seconds: float | None = None
    final_answer: str | None = None
    reason: str | None = None      # only for skipped
    tools_fingerprint: str | None = None   # the suite's tools (Step A.1); None = NOT RECORDED (unknown)
    tools: list[ToolSpec] | None = None    # the snapshot itself, e.g. to show "calculator v2"


@dataclass(frozen=True)
class SaveOutcome:
    """What happened when a finished benchmark was persisted. Execution already succeeded."""

    saved: bool
    suite_id: str
    error: str | None = None
    recovery_path: Path | None = None   # JSON copy written because the database save failed


def tool_hash(spec: ToolSpec) -> str:
    return hashlib.sha256(canonical_json(spec.model_dump()).encode("utf-8")).hexdigest()


def task_hash(task: Task) -> str:
    return hashlib.sha256(task.model_dump_json().encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    # Stored in UTC so that text order == time order ("newest first" can sort the strings).
    if value is None:
        return None
    return (value.astimezone(timezone.utc) if value.tzinfo else value).isoformat()


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
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(f"results database has schema version {version}; this code "
                                     f"understands up to version {SCHEMA_VERSION} (update AgentBench?)")
        if version == 0 and self._conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]:
            raise SchemaVersionError("this file already contains tables but no AgentBench schema "
                                     "version - refusing to use it as a results database")
        if version != 0 and version not in MIGRATIONS:
            raise SchemaVersionError(f"no migration from schema version {version}")
        # ONE transaction: create (if new) + every migration + the new version number.
        # If any statement fails, ROLLBACK leaves the file exactly as it was (old version, old data).
        # (PRAGMA cannot take "?" parameters; the versions are integers from our own code.)
        script = [SCHEMA] if version == 0 else []
        script += [MIGRATIONS[v] for v in range(max(version, 1), SCHEMA_VERSION)]
        try:
            self._conn.executescript("BEGIN;\n" + "\n".join(script)
                                     + f"\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;")
        except sqlite3.Error as exc:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise StorageError(f"could not upgrade the results database from version {version} to "
                               f"{SCHEMA_VERSION}; nothing was changed: {exc}") from exc

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

        if suite.tools is not None:  # None = not recorded: leave tools_recorded = 0, write no rows
            self._conn.execute("UPDATE suite_runs SET tools_recorded = 1 WHERE suite_id = ?", (suite.suite_id,))
            for position, spec in enumerate(suite.tools):
                digest = tool_hash(spec)
                self._conn.execute(  # the same tool spec seen before -> already stored once
                    "INSERT INTO tool_versions (tool_hash, name, version, spec_json) VALUES (?, ?, ?, ?)"
                    " ON CONFLICT (tool_hash) DO NOTHING",
                    (digest, spec.name, spec.version, canonical_json(spec.model_dump())))
                self._conn.execute("INSERT INTO suite_tools (suite_id, position, tool_hash) VALUES (?, ?, ?)",
                                   (suite.suite_id, position, digest))

    def _insert_record(self, suite_id: str, position: int, record: RunRecord) -> None:
        run, ev = record.run, record.evaluation
        self._conn.execute(
            "INSERT INTO run_records (run_id, suite_id, position, task_id, repeat_index, difficulty,"
            " outcome, status, final_answer, duration_seconds, error, error_kind, llm_calls,"
            " evaluation_passed, retries_recorded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run.run_id, suite_id, position, record.task_id, record.repeat, record.difficulty,
             record.outcome, run.status, run.final_answer, run.duration_seconds, run.error,
             run.error_kind, run.llm_calls, None if ev is None else int(ev.passed),
             int(run.retries is not None)))
        self._conn.executemany(
            "INSERT INTO retries (run_id, position, step_index, attempt, error_kind, status_code,"
            " waited_seconds, request_id, occurred_at, succeeded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(run.run_id, i, r.step_index, r.attempt, r.error_kind, r.status_code, r.waited_seconds,
              r.request_id, _iso(r.occurred_at), int(r.succeeded)) for i, r in enumerate(run.retries or [])])
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

    def suite_identity(self, suite_id: str) -> tuple[list[str], list[Task], list[ToolSpec] | None, str | None]:
        """(scheduled task ids, stored task definitions, tool snapshot, dataset) - without loading traces.
        Task definitions can be [] for results stored without them; tools None = not recorded."""
        row = self._conn.execute("SELECT dataset FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone()
        if row is None:
            raise SuiteNotFoundError(f"no suite with id {suite_id!r}")
        scheduled = self._conn.execute(
            "SELECT st.task_id, tv.definition_json FROM suite_tasks st"
            " LEFT JOIN task_versions tv ON tv.task_hash = st.task_hash"
            " WHERE st.suite_id = ? ORDER BY st.position", (suite_id,)).fetchall()
        tasks = [Task.model_validate_json(r["definition_json"]) for r in scheduled if r["definition_json"]]
        return [r["task_id"] for r in scheduled], tasks, self.suite_tools(suite_id), row["dataset"]

    @staticmethod
    def _config_from_row(row: sqlite3.Row) -> AgentConfig:
        """The stored agent configuration - ONE way to rebuild it (load() and the run list both use this)."""
        return AgentConfig(name=row["config_name"], provider=row["provider"], model=row["model"],
                           system_prompt=row["system_prompt"], max_attempts=row["max_attempts"],
                           min_interval_seconds=row["min_interval_seconds"])

    def suite_config(self, suite_id: str) -> AgentConfig:
        row = self._conn.execute("SELECT * FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone()
        if row is None:
            raise SuiteNotFoundError(f"no suite with id {suite_id!r}")
        return self._config_from_row(row)

    def load(self, suite_id: str) -> SuiteResult:
        row = self._conn.execute("SELECT * FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone()
        if row is None:
            raise SuiteNotFoundError(f"no suite with id {suite_id!r}")
        config = self._config_from_row(row)
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
            stop_reason=row["stop_reason"],
            tools=self.suite_tools(suite_id))

    def suite_tools(self, suite_id: str) -> list[ToolSpec] | None:
        """The tool snapshot of one suite; None = not recorded (stored before Step A.1), never []."""
        row = self._conn.execute("SELECT tools_recorded FROM suite_runs WHERE suite_id = ?", (suite_id,)).fetchone()
        if row is None:
            raise SuiteNotFoundError(f"no suite with id {suite_id!r}")
        if not row["tools_recorded"]:
            return None
        return [ToolSpec.model_validate_json(r["spec_json"]) for r in self._conn.execute(
            "SELECT tv.spec_json FROM suite_tools st JOIN tool_versions tv ON tv.tool_hash = st.tool_hash"
            " WHERE st.suite_id = ? ORDER BY st.position", (suite_id,))]

    def resolve(self, prefix: str) -> str:
        """Full suite_id from its first characters (like a short git commit id)."""
        if not prefix:
            raise SuiteNotFoundError("empty suite id")
        # substr() instead of LIKE: characters such as % or _ in the input stay plain text.
        rows = self._conn.execute("SELECT suite_id FROM suite_runs WHERE substr(suite_id, 1, ?) = ?",
                                  (len(prefix), prefix)).fetchall()
        if not rows:
            raise SuiteNotFoundError(f"no suite id starts with {prefix!r}")
        if len(rows) > 1:
            raise AmbiguousSuiteIdError(f"{prefix!r} matches {len(rows)} suites - type more characters")
        return rows[0]["suite_id"]

    # ---------- queries (what the dashboard will ask) ------------------------------------

    def list_suites(self, *, real_only: bool = False, limit: int | None = None) -> list[SuiteSummary]:
        """All stored suite runs, newest first, with pass/fail/infra/skipped counts from SQL."""
        rows = self._conn.execute(
            """
            SELECT s.suite_id, s.suite_name, s.config_name, s.provider, s.model, s.repeats,
                   s.started_at, s.finished_at, s.stop_reason,
                   (SELECT COUNT(*) FROM suite_tasks t WHERE t.suite_id = s.suite_id) * s.repeats
                                                                        AS scheduled_runs,
                   COALESCE(SUM(r.outcome = 'passed'), 0)               AS passed,
                   COALESCE(SUM(r.outcome = 'failed'), 0)               AS failed,
                   COALESCE(SUM(r.outcome = 'infra_error'), 0)          AS infra_errors,
                   (SELECT COUNT(*) FROM skipped_runs k WHERE k.suite_id = s.suite_id) AS skipped,
                   COALESCE(SUM(r.llm_calls), 0)                        AS total_llm_calls
            FROM suite_runs s
            LEFT JOIN run_records r ON r.suite_id = s.suite_id      -- LEFT: keep suites with 0 runs
            WHERE (? = 0 OR s.provider <> 'fake')
            GROUP BY s.suite_id
            ORDER BY s.started_at DESC, s.saved_at DESC
            LIMIT ?
            """, (int(real_only), -1 if limit is None else limit)).fetchall()   # LIMIT -1 = no limit
        return [SuiteSummary(**dict(row)) for row in rows]

    def task_history(self, task_id: str) -> list[TaskHistoryEntry]:
        """Every scheduled run of one task across all stored suites, newest suite first."""
        rows = self._conn.execute(
            """
            SELECT s.suite_id, s.started_at, s.config_name, s.provider, s.model, s.prompt_hash,
                   st.task_hash, r.repeat_index AS repeat, r.outcome, r.error_kind, r.llm_calls,
                   r.duration_seconds, r.final_answer, NULL AS reason
            FROM run_records r
            JOIN suite_runs s   ON s.suite_id = r.suite_id
            JOIN suite_tasks st ON st.suite_id = r.suite_id AND st.task_id = r.task_id
            WHERE r.task_id = ?
            UNION ALL
            SELECT s.suite_id, s.started_at, s.config_name, s.provider, s.model, s.prompt_hash,
                   st.task_hash, k.repeat_index, 'skipped', NULL, NULL, NULL, NULL, k.reason
            FROM skipped_runs k
            JOIN suite_runs s   ON s.suite_id = k.suite_id
            JOIN suite_tasks st ON st.suite_id = k.suite_id AND st.task_id = k.task_id
            WHERE k.task_id = ?
            ORDER BY 2 DESC, 8
            """, (task_id, task_id)).fetchall()
        tools = {sid: self.suite_tools(sid) for sid in {row["suite_id"] for row in rows}}   # once per suite
        return [TaskHistoryEntry(**dict(row), tools=tools[row["suite_id"]],
                                 tools_fingerprint=tools_fingerprint(tools[row["suite_id"]])) for row in rows]

    def _load_record(self, row: sqlite3.Row) -> RunRecord:
        run_id = row["run_id"]
        steps = [Step(index=s["step_index"], llm_output=s["llm_output"], timestamp=s["timestamp"],
                      input_tokens=s["input_tokens"], output_tokens=s["output_tokens"],
                      tool_call=None if s["tool_name"] is None else ToolCall(
                          tool_name=s["tool_name"], arguments=json.loads(s["tool_arguments_json"]),
                          output=s["tool_output"], error=s["tool_error"]))
                 for s in self._conn.execute(
                     "SELECT * FROM steps WHERE run_id = ? ORDER BY step_index", (run_id,))]
        retries = None  # not recorded (runs from before Phase 8): unknown, never "0 retries"
        if row["retries_recorded"]:
            retries = [RetryEvent(step_index=r["step_index"], attempt=r["attempt"], error_kind=r["error_kind"],
                                  status_code=r["status_code"], waited_seconds=r["waited_seconds"],
                                  request_id=r["request_id"], occurred_at=r["occurred_at"],
                                  succeeded=bool(r["succeeded"]))
                       for r in self._conn.execute(
                           "SELECT * FROM retries WHERE run_id = ? ORDER BY position", (run_id,))]
        run = RunResult(run_id=run_id, task_id=row["task_id"], status=row["status"],
                        final_answer=row["final_answer"], trace=Trace(task_id=row["task_id"], steps=steps),
                        duration_seconds=row["duration_seconds"], error=row["error"],
                        error_kind=row["error_kind"], llm_calls=row["llm_calls"], retries=retries)
        evaluation = None
        if row["evaluation_passed"] is not None:
            checks = [Check(name=c["name"], passed=bool(c["passed"]), reason=c["reason"])
                      for c in self._conn.execute(
                          "SELECT * FROM checks WHERE run_id = ? ORDER BY position", (run_id,))]
            evaluation = EvaluationResult(run_id=run_id, task_id=row["task_id"],
                                          passed=bool(row["evaluation_passed"]), checks=checks)
        return RunRecord(task_id=row["task_id"], repeat=row["repeat_index"], difficulty=row["difficulty"],
                         run=run, evaluation=evaluation, outcome=row["outcome"])


def save_with_recovery(suite: SuiteResult, path: str | Path = DEFAULT_RESULTS_DB,
                       recovery_dir: str | Path = RESULTS_DIR) -> SaveOutcome:
    """Persist a FINISHED benchmark. Never raises: a failed save is reported, not hidden.

    The benchmark result is not changed either way. If the database save fails, a JSON copy is
    written as a recovery path (it can be imported later with scripts/results.py import).
    """
    try:
        with ResultStore(path) as store:
            store.save(suite)
        return SaveOutcome(saved=True, suite_id=suite.suite_id)
    except (StorageError, sqlite3.Error, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    try:
        recovery = export_json(suite, recovery_dir)
    except OSError as exc:  # even the backup failed: say so, never pretend
        return SaveOutcome(saved=False, suite_id=suite.suite_id,
                           error=f"{error}; JSON recovery export also failed: {exc}")
    return SaveOutcome(saved=False, suite_id=suite.suite_id, error=error, recovery_path=recovery)

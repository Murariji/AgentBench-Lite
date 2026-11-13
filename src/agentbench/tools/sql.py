"""Read-only SQL tools for the Data Analyst agent.

The model's SQL is UNTRUSTED input (prompt injection could make it write anything).
Defence in depth; the ENGINE-LEVEL layers are the real security boundary:

  A  fixed path       the database file is chosen by OUR code; tools take no path
  B  read-only open   sqlite "mode=ro": the file cannot be written
  C  query_only       PRAGMA query_only = ON: a second, independent write block
  D  authorizer       SQLite asks us before every action; ALLOWLIST: select, read,
                      functions, recursive CTEs. Everything else (writes, schema
                      changes, ATTACH, PRAGMA, transactions...) is denied
  E  no extensions    extension loading disabled; load_extension() also denied in D
  F  size limits      max string/blob size, max SQL length, 0 attached databases
  G  time limit       progress handler interrupts long queries (APPROXIMATE: checked
                      every N virtual-machine steps, not a strict wall-clock timeout)
  H  one statement    Python's sqlite3 refuses "SELECT 1; DROP ..." by itself
Our-code layers (helpful messages + token protection, NOT security):
  I  SELECT/WITH check   clear error so the model can correct itself
  J  row limit           at most max_rows rows returned
  K  output limits       long cells cut, total output capped

Honest limitations: this is a constrained read-only SQL tool, not an operating-system
sandbox. It does not protect against bugs inside SQLite itself; everything stored in
the database is readable by the agent (never put secrets in it); the time limit is
approximate; and it cannot stop semantically WRONG queries (that's what we benchmark).
"""

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from agentbench.tools.base import Tool, ToolError

# D: the authorizer allowlist. Anything not listed here is denied.
_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,      # run a SELECT
    sqlite3.SQLITE_READ,        # read a column of a table
    sqlite3.SQLITE_FUNCTION,    # call a function (COUNT, SUM, strftime, ...) - see below
    sqlite3.SQLITE_RECURSIVE,   # WITH RECURSIVE ...
}
_DENIED_FUNCTIONS = {"load_extension"}  # E: even if extensions were enabled

_LEADING_COMMENTS = re.compile(r"^(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", re.DOTALL)


def _authorizer(action: int, arg1: Any, arg2: Any, db_name: Any, trigger: Any) -> int:
    if action not in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in _DENIED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class ReadOnlySQLite:
    """One read-only, locked-down connection to a fixed database file."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_rows: int = 50,
        max_cell_chars: int = 200,
        max_output_chars: int = 4000,
        time_limit: float = 2.0,
        max_value_bytes: int = 1_000_000,
        max_sql_chars: int = 5_000,
    ) -> None:
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"database not found: {path} (build it first)")
        self.path = path
        self.max_rows, self.max_cell_chars = max_rows, max_cell_chars
        self.max_output_chars, self.time_limit = max_output_chars, time_limit

        # B: read-only at the file level.
        self._conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        # E: extension loading off (it is off by default; we make it explicit).
        if hasattr(self._conn, "enable_load_extension"):
            self._conn.enable_load_extension(False)
        # C: second, independent write block.
        self._conn.execute("PRAGMA query_only = ON")
        # Schema for list_tables / describe_table, read ONCE with this trusted code.
        tables = [r[0] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        self.schema: dict[str, list[tuple[str, str]]] = {
            t: [(c[1], c[2]) for c in self._conn.execute(f'PRAGMA table_info("{t}")')] for t in tables
        }
        # F: size limits.
        self._conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, max_value_bytes)
        self._conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, max_sql_chars)
        self._conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        # D: from now on, SQLite asks _authorizer before every action.
        self._conn.set_authorizer(_authorizer)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ReadOnlySQLite":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------- running a query ------------------------------------------------

    def query(self, sql: str) -> str:
        """Layer I (friendly SELECT/WITH check), then the engine-protected run."""
        body = _LEADING_COMMENTS.sub("", sql or "").strip()
        first_word = body.split(None, 1)[0].upper() if body else ""
        if first_word not in ("SELECT", "WITH"):
            raise ToolError("Only read-only SELECT queries (optionally starting with WITH) are allowed.")
        return self._run(sql)

    def _run(self, sql: str) -> str:
        """Execute with engine-level protection only. Tests call this directly to prove
        the engine blocks attacks even when the text check (layer I) is bypassed."""
        deadline = time.monotonic() + self.time_limit
        # G: return non-zero -> SQLite interrupts the query. Checked every 1000 VM steps.
        self._conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            cursor = self._conn.execute(sql)
            rows = cursor.fetchmany(self.max_rows + 1)  # J: one extra row tells us "there's more"
            columns = [d[0] for d in cursor.description or []]
            cursor.close()
        except sqlite3.ProgrammingError as exc:  # H: e.g. more than one statement
            raise ToolError(f"query rejected: {exc}") from None
        except sqlite3.DatabaseError as exc:
            raise ToolError(self._explain(str(exc))) from None
        finally:
            self._conn.set_progress_handler(None, 0)
        return self._format(columns, rows)

    def _explain(self, message: str) -> str:
        lowered = message.lower()
        if "interrupted" in lowered:
            return (f"query stopped: it ran longer than about {self.time_limit:g}s "
                    "(simplify it, add WHERE/LIMIT, or aggregate)")
        if "not authorized" in lowered:
            return "query blocked: only reading data is allowed (not authorized)"
        if "readonly" in lowered or "read-only" in lowered:
            return "query blocked: the database is read-only"
        if "too big" in lowered or "too long" in lowered:
            return f"query blocked: value or SQL too large ({message})"
        return f"SQL error: {message}"

    # ---------- formatting (layers J and K) ------------------------------------

    def _cell(self, value: Any) -> str:
        if value is None:
            text = "NULL"
        elif isinstance(value, bytes):
            text = f"<blob {len(value)} bytes>"
        else:
            text = str(value).replace("\n", " ")
        if len(text) > self.max_cell_chars:
            text = text[: self.max_cell_chars] + "…"
        return text

    def _format(self, columns: list[str], rows: list[tuple]) -> str:
        more = len(rows) > self.max_rows
        rows = rows[: self.max_rows]
        lines = [" | ".join(columns)] + [" | ".join(self._cell(v) for v in row) for row in rows]
        if more:
            footer = (f"(showing the first {self.max_rows} rows; more rows exist - "
                      "use WHERE, LIMIT or aggregates)")
        else:
            footer = f"({len(rows)} row{'s' if len(rows) != 1 else ''})"
        text = "\n".join(lines + [footer])
        if len(text) > self.max_output_chars:
            notice = f"\n... output truncated at {self.max_output_chars} characters"
            cut = text[: self.max_output_chars - len(notice)]
            text = cut[: cut.rfind("\n")] + notice if "\n" in cut else cut + notice
        return text


# ---------- the three tools the agent sees ------------------------------------

class ListTablesTool(Tool):
    name = "list_tables"
    version = 1
    description = "List the tables in the shop database. Use this first to explore the data."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, db: ReadOnlySQLite) -> None:
        self._db = db

    def run(self) -> str:
        return ", ".join(self._db.schema)


class DescribeTableTool(Tool):
    name = "describe_table"
    version = 1
    description = "Show the columns and types of one table in the shop database."
    parameters = {
        "type": "object",
        "properties": {"table": {"type": "string", "description": "Table name, e.g. 'orders'"}},
        "required": ["table"],
    }

    def __init__(self, db: ReadOnlySQLite) -> None:
        self._db = db

    def run(self, table: str) -> str:
        columns = self._db.schema.get(table.strip())
        if columns is None:
            raise ToolError(f"no such table {table!r}; available: {', '.join(self._db.schema)}")
        return "\n".join(f"{name} {type_}" for name, type_ in columns)


class SqlQueryTool(Tool):
    name = "sql_query"
    version = 1
    description = (
        "Run ONE read-only SQLite SELECT query on the shop database and get the rows back. "
        "Dates are TEXT 'YYYY-MM-DD' (use strftime). At most 50 rows are returned, so "
        "prefer aggregates (COUNT, SUM, GROUP BY) over SELECT *."
    )
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "A single SQLite SELECT statement"}},
        "required": ["query"],
    }

    def __init__(self, db: ReadOnlySQLite) -> None:
        self._db = db

    def run(self, query: str) -> str:
        return self._db.query(query)


def sql_tools(db: ReadOnlySQLite) -> list[Tool]:
    """The three Data Analyst tools, all sharing one locked-down connection."""
    return [ListTablesTool(db), DescribeTableTool(db), SqlQueryTool(db)]

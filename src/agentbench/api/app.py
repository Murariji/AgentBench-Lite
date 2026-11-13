"""AgentBench-Lite web API - 9.1 read-only endpoints + 9.2 background runs behind safety gates.

    app = create_app("data/results.db")       # served on 127.0.0.1 by scripts/serve_api.py

Rules:
  * No agent or evaluation logic lives here: every endpoint calls the existing framework
    (ResultStore, compute_metrics, analyze_suite, measure_task, comparison_conclusions, check_suite).
  * Each request gets its OWN ResultStore (SQLite connection) through dependency injection,
    opened for that request and closed after it - connections are never shared between threads.
  * Every error has one shape: {"error": {"code", "message", "details"}}.
  * GET endpoints never change anything.
  * Runs (9.2): POST /runs starts ONE run at a time in the background (202 + job id). SCRIPTED runs are
    always allowed. A REAL Gemini run needs ALL FOUR gates: server started with --allow-real-runs,
    confirm=true, a budget within the server's maximum, and a passing registration guard. The real
    client is created only inside the job, after the gates - and never in tests (it is injected).
"""

import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path as FilePath

from fastapi import Body, Depends, FastAPI, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentbench.analysis import analyze_run, analyze_suite
from agentbench.api.jobs import JobManager, RunInProgressError
from agentbench.api.middleware import MAX_BODY_BYTES, BodySizeLimit
from agentbench.api.schemas import (CompareOut, ErrorResponse, EstimateOut, FailuresOut, HealthOut, HistoryPage,
                                    IndexOut, JobOut, JobPage, MeasureGroupOut, MeasureOut, Pagination, RateOut,
                                    RegisteredSuiteOut, RegistrationOut, RunDetailOut, RunIn, RunSummaryOut,
                                    SuiteDetailOut, SuitePage, SuiteSummaryOut, TaskOutcomesOut)
from agentbench.datasets import DEFAULT_DB_PATH
from agentbench.report import RESULTS_DIR
from agentbench.runs import RunPlan, RunRequestError, gemini_client, gemini_config, plan_run, redact, scripted_parts
from agentbench.measurement import MEASURE_LIMITATIONS, measure_task
from agentbench.metrics import compute_metrics
from agentbench.models import SuiteResult, tasks_fingerprint, tools_fingerprint
from agentbench.registration import check_suite, registrations_for
from agentbench.report import CONFIG_DIMENSIONS, FAIRNESS_DIMENSIONS, comparison_conclusions
from agentbench.storage import (DEFAULT_RESULTS_DB, SCHEMA_VERSION, AmbiguousSuiteIdError, ResultStore,
                                StorageError, SuiteNotFoundError)
from agentbench.suites import SUITES

# Ids in URLs: letters, digits, '-' and '_' only. Suite ids may be shortened, but to at least 4 characters.
SUITE_ID = r"^[0-9A-Za-z_-]{4,64}$"
TASK_ID = r"^[0-9A-Za-z_.-]{1,64}$"
MAX_LIMIT = 100
MAX_COMPARE = 5
JOB_ID = r"^[0-9a-f]{4,32}$"
DEFAULT_MAX_REAL_BUDGET = 100
API_VERSION = "0.9.3"
# The React dev server (Phase 10) runs here. Only these origins may READ responses in a browser.
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
_ORIGIN = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{1,5})?$")      # scheme://host[:port], nothing else


def validate_origins(origins) -> list[str]:
    """Explicit origins only: never '*', no paths, no trailing slash."""
    result = []
    for origin in origins:
        if origin == "*" or not _ORIGIN.match(origin):
            raise ValueError(f"invalid CORS origin {origin!r}: use an exact origin like http://localhost:5173 "
                             "(no '*', no path)")
        result.append(origin)
    return result


def check_startup(db_path) -> str | None:
    """Can the results database be opened (and, if needed, upgraded)? None = yes, else a clear message."""
    try:
        ResultStore(db_path).close()
    except StorageError as exc:
        return f"cannot use the results database {db_path}: {exc}"
    except OSError as exc:
        return f"cannot open the results database {db_path}: {exc}"
    return None


# OpenAPI examples. They only PRE-FILL the /docs form; nothing is sent until a person clicks Execute, and
# the server checks every gate exactly as for any other client - Swagger cannot bypass them.
RUN_EXAMPLES = {
    "scripted": {"summary": "Scripted run: careful agent on shop-hard (free, always allowed)",
                 "description": "A SCRIPTED test agent (fixed answers, not AI). No model is called.",
                 "value": {"agent": "careful", "suite": "shop-hard"}},
    "scripted_subset": {"summary": "Scripted run: sloppy agent on two tasks (free)",
                        "description": "Falls into its planted traps on purpose: useful to see failure analysis.",
                        "value": {"agent": "sloppy", "suite": "shop-hard", "tasks": ["hard-001", "hard-007"]}},
    "real_pilot_gated": {
        "summary": "REAL Gemini run - only if the server was started with --allow-real-runs (uses free quota)",
        "description": "Sends REAL requests to Gemini if, and only if, ALL gates pass on the server: started "
                       "with --allow-real-runs, confirm=true, a budget within --max-real-budget, and a passing "
                       "registration guard. Otherwise the server answers 403/422/409 and sends nothing. "
                       "Try POST /estimates first.",
        "value": {"agent": "gemini", "suite": "shop-hard", "tasks": ["hard-001", "hard-007"],
                  "budget": 25, "confirm": True}},
}
# Every error uses ErrorResponse. Each endpoint documents exactly the codes it can really return.
_ERROR_TEXT = {
    403: "Real Gemini runs are disabled on this server (start it with --allow-real-runs).",
    404: "Unknown suite, run, task or job.",
    409: "Conflict: ambiguous short id, incompatible comparison, not analysable, registration mismatch, "
         "or a run already in progress.",
    413: "The request body is larger than 64 KB.",
    422: "Invalid input (wrong format, out of range, a missing safety confirmation or budget).",
    500: "Unexpected server error (only its type is reported - never a traceback or a secret).",
    503: "The results database cannot be used.",
}


def errors(*codes: int) -> dict:
    return {code: {"model": ErrorResponse, "description": _ERROR_TEXT[code]} for code in (*codes, 500)}


def default_real_llm_factory():
    """(model id, LLM factory) for a REAL Gemini run. Called only inside a job, after all four gates."""
    client = gemini_client()
    return client.model, (lambda task, repeat: client)


class ApiError(Exception):
    """Raised by endpoints; turned into {"error": {...}} with the given HTTP status code."""

    def __init__(self, status: int, code: str, message: str, details=None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": jsonable_encoder(details)}}
    return JSONResponse(status_code=status, content=body)


def _paginate(items: list, limit: int, offset: int) -> tuple[list, Pagination]:
    page = items[offset:offset + limit]
    nxt = offset + limit if offset + limit < len(items) else None
    return page, Pagination(limit=limit, offset=offset, total=len(items), returned=len(page), next_offset=nxt)


def _kind(provider: str) -> str:
    return "scripted" if provider == "fake" else "real"


def _rate(passed: int, eligible: int, text: str) -> RateOut:
    return RateOut(passed=passed, eligible=eligible, rate=passed / eligible if eligible else None, text=text)


def _registration(suite: SuiteResult) -> RegistrationOut:
    if not suite.tasks:
        return RegistrationOut(status="unknown", line="cannot verify (no task definitions stored)",
                               problems=[], notes=["no task definitions stored"])
    g = check_suite(suite.suite_name, suite.tasks, suite.tools, suite.dataset)
    r = g.registration or {}
    return RegistrationOut(status=g.status, line=g.line(), problems=g.problems, notes=g.notes,
                           version=r.get("version"), suite_fingerprint=r.get("suite_fingerprint"))


def run_identity(suite_name: str, task_ids: list[str], tasks: list, tools, dataset) -> dict:
    """tasks_fingerprint, registration_status and scope of one stored run - honestly:
    without stored task definitions everything is "unknown" (never assumed to be a full-suite run).

      registered suite   -> registration guard: matches = full, subset = subset; differs: scope from the
                            task ids against the newest registration (the definitions differ either way)
      unregistered suite -> scope from the run's task ids against the suite's current task list
    """
    if not tasks:
        return {"tasks_fingerprint": None, "registration_status": "unknown", "scope": "unknown"}
    guard = check_suite(suite_name, tasks, tools, dataset)
    if guard.status in ("matches", "subset"):
        scope = "full" if guard.status == "matches" else "subset"
    else:
        if guard.status == "differs":
            reference = [t["id"] for t in guard.registration["tasks"]]
        else:
            reference = [t.id for t in SUITES.get(suite_name, [])]
        if not reference:
            scope = "unknown"                                  # a suite this code does not know
        elif task_ids == reference:
            scope = "full"
        elif set(task_ids) < set(reference):
            scope = "subset"
        else:
            scope = "unknown"                                  # tasks the current suite does not contain
    return {"tasks_fingerprint": tasks_fingerprint(tasks), "registration_status": guard.status, "scope": scope}


def _list_fingerprints(store: ResultStore, suite_name: str, suite_id: str) -> dict:
    """Everything the run list says about WHAT ran - all from stored data, using the existing formulas:
    AgentConfig.config_fingerprint and models.tools_fingerprint (None when tools were not recorded)."""
    task_ids, tasks, tools, dataset = store.suite_identity(suite_id)
    return {**run_identity(suite_name, task_ids, tasks, tools, dataset),
            "config_fingerprint": store.suite_config(suite_id).config_fingerprint,
            "tools_fingerprint": tools_fingerprint(tools)}


def _known_task(store: ResultStore, task_id: str) -> None:
    in_suites = any(t.id == task_id for tasks in SUITES.values() for t in tasks)
    if not in_suites and not store.task_history(task_id):
        raise ApiError(404, "not_found", f"unknown task {task_id!r}",
                       {"known_suites": {name: [t.id for t in tasks] for name, tasks in SUITES.items()}})


def create_app(db_path: str | FilePath = DEFAULT_RESULTS_DB, *, allow_real_runs: bool = False,
               max_real_budget: int = DEFAULT_MAX_REAL_BUDGET,
               real_llm_factory: Callable[[], tuple] = default_real_llm_factory,
               shop_db_path: str | FilePath = DEFAULT_DB_PATH, recovery_dir: str | FilePath = RESULTS_DIR,
               sleep: Callable[[float], None] = time.sleep,
               cors_origins=DEFAULT_CORS_ORIGINS, max_body_bytes: int = MAX_BODY_BYTES) -> FastAPI:
    """Everything the app depends on is injected: tests pass a temporary database, a fake "real" LLM
    factory and a no-op sleep, so no real client is ever built and nothing waits."""
    if max_real_budget < 1:
        raise ValueError("max_real_budget must be at least 1")
    origins = validate_origins(cors_origins)
    app = FastAPI(
        title="AgentBench-Lite API",
        version=API_VERSION,
        description="Stored benchmark runs, traces, failure analysis and comparisons, plus background runs "
                    "(one at a time). Scripted runs are fixed test fixtures, not AI. Real Gemini runs are OFF "
                    "unless the server is started with --allow-real-runs. Local use only (127.0.0.1).",
    )
    app.state.db_path = FilePath(db_path)
    app.state.allow_real_runs = allow_real_runs
    app.state.max_real_budget = max_real_budget
    app.state.jobs = JobManager(results_db=FilePath(db_path), recovery_dir=FilePath(recovery_dir), sleep=sleep)
    app.state.cors_origins = origins

    # ---------- middleware (outermost last): CORS wraps the body limit, so even a 413 carries CORS headers --
    app.add_middleware(BodySizeLimit, limit=max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False, max_age=600)

    @app.middleware("http")
    async def _no_cache_for_live_data(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/runs", "/estimates")):
            response.headers["Cache-Control"] = "no-store"      # a progress bar must never show a cached status
        return response

    # ---------- dependency injection: one ResultStore per request ----------------------------
    def get_store() -> Iterator[ResultStore]:
        # One connection per request. FastAPI can run this setup and the close() below in DIFFERENT worker
        # threads, so SQLite's same-thread check is off for this connection (it is never shared).
        store = ResultStore(app.state.db_path, check_same_thread=False)
        try:
            yield store
        finally:
            store.close()

    def load_suite(store: ResultStore, suite_id: str) -> SuiteResult:
        try:
            return store.load(store.resolve(suite_id))
        except AmbiguousSuiteIdError as exc:
            raise ApiError(409, "ambiguous_id", str(exc), {"suite_id": suite_id}) from None
        except SuiteNotFoundError as exc:
            raise ApiError(404, "not_found", str(exc), {"suite_id": suite_id}) from None

    # ---------- one error shape for everything ---------------------------------------------------
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return _error(422, "validation_error", "the request is invalid", exc.errors())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(StorageError)
    async def _storage_error(request: Request, exc: StorageError):
        return _error(503, "storage_unavailable", redact(str(exc)))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Never a traceback, never a secret: only the error type.
        response = _error(500, "internal_error", f"unexpected server error ({type(exc).__name__})")
        # This handler runs OUTSIDE the CORS middleware, so add the header here for an allowed origin:
        # otherwise the browser hides this JSON and reports a misleading "CORS" network error instead.
        origin = request.headers.get("origin")
        if origin in app.state.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    # ---------- endpoints ------------------------------------------------------------------------
    @app.get("/", response_model=IndexOut, responses=errors(), tags=["meta"])
    def index() -> dict:
        return {"name": "AgentBench-Lite API", "version": API_VERSION, "docs": "/docs", "health": "/health",
                "real_runs_enabled": app.state.allow_real_runs, "local_only": "127.0.0.1"}

    @app.get("/health", response_model=HealthOut, responses=errors(503), tags=["meta"])
    def health(store: ResultStore = Depends(get_store)) -> HealthOut:
        return HealthOut(status="ok", schema_version=SCHEMA_VERSION, real_runs_enabled=app.state.allow_real_runs)

    @app.get("/registrations", response_model=list[RegisteredSuiteOut], responses=errors(), tags=["meta"])
    def registrations() -> list[RegisteredSuiteOut]:
        return [RegisteredSuiteOut(**{k: r.get(k) for k in RegisteredSuiteOut.model_fields if k != "tasks"},
                                   tasks=[t["id"] for t in r["tasks"]])
                for name in SUITES for r in registrations_for(name)]

    @app.get("/suites", response_model=SuitePage, responses=errors(422, 503), tags=["suites"])
    def list_suites(real_only: bool = False,
                    limit: int = Query(20, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0),
                    store: ResultStore = Depends(get_store)) -> SuitePage:
        rows, pagination = _paginate(store.list_suites(real_only=real_only), limit, offset)
        items = [SuiteSummaryOut(
            **row.model_dump(), short_id=row.suite_id[:8], kind=_kind(row.provider),
            pass_rate=_rate(row.passed, row.passed + row.failed, str(row.pass_rate)), complete=row.complete,
            **_list_fingerprints(store, row.suite_name, row.suite_id))
            for row in rows]                                  # computed for THIS page only (<= 100 runs)
        return SuitePage(items=items, pagination=pagination)

    @app.get("/suites/{suite_id}", response_model=SuiteDetailOut, responses=errors(404, 409, 422, 503),
             tags=["suites"])
    def get_suite(suite_id: str = Path(pattern=SUITE_ID),
                  store: ResultStore = Depends(get_store)) -> SuiteDetailOut:
        s = load_suite(store, suite_id)
        m = compute_metrics(s)
        runs = [RunSummaryOut(
            run_id=r.run.run_id, task_id=r.task_id, repeat=r.repeat, difficulty=r.difficulty, outcome=r.outcome,
            status=r.run.status, final_answer=r.run.final_answer, steps=len(r.run.trace.steps),
            llm_calls=r.run.llm_calls, retries=None if r.run.retries is None else len(r.run.retries),
            duration_seconds=r.run.duration_seconds, error_kind=r.run.error_kind,
            failed_checks=[c.name for c in r.evaluation.checks if not c.passed] if r.evaluation else [])
            for r in s.records]
        return SuiteDetailOut(
            suite_id=s.suite_id, suite_name=s.suite_name, kind=_kind(s.config.provider), config=s.config,
            config_fingerprint=s.config.config_fingerprint, repeats=s.repeats, started_at=s.started_at,
            finished_at=s.finished_at, dataset=s.dataset, tools=s.tools, tools_fingerprint=s.tools_fingerprint,
            tasks_fingerprint=s.tasks_fingerprint, request_budget=s.request_budget,
            estimated_requests=s.estimated_requests, stop_reason=s.stop_reason, complete=m.complete, metrics=m,
            registration=_registration(s), runs=runs, skipped=s.skipped)

    @app.get("/suites/{suite_id}/runs/{run_id}", response_model=RunDetailOut,
             responses=errors(404, 409, 422, 503), tags=["suites"])
    def get_run(suite_id: str = Path(pattern=SUITE_ID), run_id: str = Path(pattern=SUITE_ID),
                store: ResultStore = Depends(get_store)) -> RunDetailOut:
        s = load_suite(store, suite_id)
        matches = [r for r in s.records if r.run.run_id.startswith(run_id)]
        if not matches:
            raise ApiError(404, "not_found", f"suite {s.suite_id[:8]} has no run starting with {run_id!r}",
                           {"suite_id": s.suite_id, "run_id": run_id})
        if len(matches) > 1:
            raise ApiError(409, "ambiguous_id", f"{run_id!r} matches {len(matches)} runs - type more characters")
        record = matches[0]
        task = next((t for t in s.tasks if t.id == record.task_id), None)
        return RunDetailOut(suite_id=s.suite_id, record=record,
                            analysis=analyze_run(task, record) if task else None)

    @app.get("/suites/{suite_id}/failures", response_model=FailuresOut, responses=errors(404, 409, 422, 503),
             tags=["suites"])
    def get_failures(suite_id: str = Path(pattern=SUITE_ID),
                     store: ResultStore = Depends(get_store)) -> FailuresOut:
        s = load_suite(store, suite_id)
        if not s.tasks:
            raise ApiError(409, "not_analysable", "this suite stored no task definitions, so it cannot be analysed",
                           {"suite_id": s.suite_id})
        return FailuresOut(note="Rule-based, from the stored trace: likely patterns, not the model's reasoning. "
                                "Infrastructure errors are not agent failures.", analysis=analyze_suite(s))

    @app.get("/tasks/{task_id}/history", response_model=HistoryPage, responses=errors(404, 422, 503),
             tags=["tasks"])
    def task_history(task_id: str = Path(pattern=TASK_ID),
                     limit: int = Query(20, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0),
                     store: ResultStore = Depends(get_store)) -> HistoryPage:
        _known_task(store, task_id)
        items, pagination = _paginate(store.task_history(task_id), limit, offset)
        return HistoryPage(task_id=task_id, items=items, pagination=pagination)

    @app.get("/tasks/{task_id}/measure", response_model=MeasureOut, responses=errors(404, 422, 503),
             tags=["tasks"])
    def task_measure(task_id: str = Path(pattern=TASK_ID),
                     store: ResultStore = Depends(get_store)) -> MeasureOut:
        _known_task(store, task_id)
        groups = measure_task(store, task_id)
        sizes = ", ".join(f"{g.eligible} evaluated" for g in groups) or "no runs"
        return MeasureOut(
            task_id=task_id,
            groups=[MeasureGroupOut(
                provider=g.provider, model=g.model, kind=_kind(g.provider), tools=g.tools, calculator=g.calculator,
                suites=len(g.suites), scheduled=g.scheduled, passed=g.passed, evaluated=g.eligible,
                infra_errors=g.infra_errors, skipped=g.skipped,
                avg_llm_calls=sum(g.llm_calls) / len(g.llm_calls) if g.llm_calls else None,
                avg_steps=sum(g.steps) / len(g.steps) if g.steps else None,
                runs_with_round_errors=g.runs_with_round_errors, round_errors=g.round_errors,
                tool_errors=g.tool_errors, near_step_limit=g.near_step_limit,
                step_limit_failures=g.step_limit_failures) for g in groups],
            limitations=[f"Tiny samples ({sizes}): exploratory evidence, not statistical proof.",
                         *MEASURE_LIMITATIONS])

    @app.get("/compare", response_model=CompareOut, responses=errors(404, 409, 422, 503), tags=["suites"])
    def compare_suites(ids: list[str] = Query(..., description=f"2 to {MAX_COMPARE} suite ids (repeat ?ids=)"),
                       store: ResultStore = Depends(get_store)) -> CompareOut:
        bad = [i for i in ids if not re.fullmatch(SUITE_ID, i)]
        if bad:
            raise ApiError(422, "validation_error", "invalid suite id(s)", {"ids": bad})
        if not 2 <= len(ids) <= MAX_COMPARE:
            raise ApiError(422, "validation_error",
                           f"a comparison needs 2 to {MAX_COMPARE} suite ids (got {len(ids)})")
        suites = [load_suite(store, i) for i in ids]
        full_ids = [s.suite_id for s in suites]
        if len(set(full_ids)) != len(full_ids):
            raise ApiError(422, "validation_error", "the same run was given more than once", {"ids": ids})
        names = sorted({s.suite_name for s in suites})
        if len(names) > 1:
            raise ApiError(409, "incompatible_comparison",
                           "runs of different suites cannot be compared: " + ", ".join(names),
                           {"suite_names": {s.suite_id[:8]: s.suite_name for s in suites}})
        metrics = [compute_metrics(s) for s in suites]
        conclusions = comparison_conclusions(suites, metrics)
        outcomes = [{(r.task_id, r.repeat): r.outcome for r in s.records} for s in suites]
        tasks = [TaskOutcomesOut(task_id=t, outcomes=(values := [o.get((t, 0), "skipped") for o in outcomes]),
                                 differs=len(set(values)) > 1) for t in suites[0].task_ids]
        return CompareOut(
            suite_ids=full_ids, fair=conclusions["fair"], unfair_dimensions=conclusions["unfair_dimensions"],
            changed_dimensions=conclusions["changed_dimensions"], tools_status=conclusions["tools_status"],
            conclusions=conclusions["lines"],
            dimensions={label: [str(get(s)) for s in suites]
                        for label, get in {**CONFIG_DIMENSIONS, **FAIRNESS_DIMENSIONS}.items()},
            metrics=metrics, tasks=tasks)

    # ---------- 9.2: estimates and background runs ------------------------------------------------------
    def make_plan(body: RunIn) -> RunPlan:
        try:
            return plan_run(body.agent, body.suite, body.tasks, repeats=body.repeats,
                            budget=body.budget if body.agent == "gemini" else None, db_path=shop_db_path)
        except RunRequestError as exc:
            raise ApiError(422, "validation_error", str(exc), {"field": exc.field}) from None

    def gate_failures(body: RunIn, plan: RunPlan) -> list[tuple[int, str, str]]:
        """Every reason a run must NOT start, as (status, code, message) - empty = allowed."""
        problems = []
        if plan.is_real:
            if not app.state.allow_real_runs:
                problems.append((403, "real_runs_disabled", "real Gemini runs are disabled on this server "
                                 "(start it with --allow-real-runs to enable them)"))
            if not body.confirm:
                problems.append((422, "confirmation_required", "a real run needs confirm=true"))
            if body.budget is None:
                problems.append((422, "budget_required", "a real run needs a budget (the hard request cap)"))
            elif body.budget > app.state.max_real_budget:
                problems.append((422, "budget_too_high", f"budget {body.budget} is above this server's maximum "
                                 f"of {app.state.max_real_budget} requests"))
        if plan.guard.blocks_real_runs and plan.is_real:
            problems.append((409, "registration_mismatch", plan.guard.line()))
        return problems

    @app.post("/estimates", response_model=EstimateOut, responses=errors(413, 422), tags=["runs"])
    def estimate(body: RunIn = Body(openapi_examples=RUN_EXAMPLES)) -> EstimateOut:
        """What a run would cost and whether it would be allowed. Never sends anything."""
        plan = make_plan(body)
        g = plan.guard
        r = g.registration or {}
        est = plan.estimate
        return EstimateOut(
            agent=body.agent, kind="real" if plan.is_real else "scripted", suite=plan.suite,
            tasks=[t.id for t in plan.tasks], runs=plan.total_runs,
            estimate=None if est is None else {"typical_requests": est.typical_requests,
                                               "worst_case_requests": est.worst_case_requests,
                                               "budget": est.budget, "estimated_seconds": est.estimated_seconds},
            registration=RegistrationOut(status=g.status, line=g.line(), problems=g.problems, notes=g.notes,
                                         version=r.get("version"), suite_fingerprint=r.get("suite_fingerprint")),
            real_runs_enabled=app.state.allow_real_runs, allowed=not gate_failures(body, plan),
            reasons=[message for _, _, message in gate_failures(body, plan)])

    @app.post("/runs", status_code=202, response_model=JobOut, responses=errors(403, 409, 413, 422),
              tags=["runs"])
    def start_run(response: Response, body: RunIn = Body(openapi_examples=RUN_EXAMPLES)) -> JobOut:
        """Start a run in the background (one at a time). Poll GET /runs/{job_id} for progress."""
        plan = make_plan(body)
        failures = gate_failures(body, plan)
        if failures:                                       # the FIRST failing gate decides the status code
            status, code, message = failures[0]
            raise ApiError(status, code, message, {"all_reasons": [m for _, _, m in failures]})
        if plan.is_real:
            def prepare():
                model, make_llm = real_llm_factory()         # built HERE (in the job), after every gate
                return gemini_config(model), make_llm
        else:
            def prepare():
                return scripted_parts(body.agent)
        try:
            job = app.state.jobs.start(plan, prepare)
        except RunInProgressError as exc:
            raise ApiError(409, "run_in_progress", str(exc), {"active_job_id": exc.active.id}) from None
        response.headers["Location"] = f"/runs/{job.id}"
        return JobOut(**app.state.jobs.get(job.id))

    @app.get("/runs", response_model=JobPage, responses=errors(422), tags=["runs"])
    def list_runs(limit: int = Query(20, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0)) -> JobPage:
        """Jobs started since THIS server started (job status is not kept across restarts)."""
        items, pagination = _paginate(app.state.jobs.list(), limit, offset)
        return JobPage(items=[JobOut(**j) for j in items], pagination=pagination)

    @app.get("/runs/{job_id}", response_model=JobOut, responses=errors(404, 422), tags=["runs"])
    def get_run_job(job_id: str = Path(pattern=JOB_ID)) -> JobOut:
        job = app.state.jobs.get(job_id)
        if job is None:
            raise ApiError(404, "not_found", f"no job {job_id!r} on this server. Job status is kept in memory "
                           "only (lost on restart); finished results are in GET /suites.", {"job_id": job_id})
        return JobOut(**job)

    return app

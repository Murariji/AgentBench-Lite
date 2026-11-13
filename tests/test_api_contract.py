"""Phase 9.3: the API contract. If test_api_matches_its_pinned_contract fails, the API changed.

Do NOT edit contract.json by hand and do not make tests rewrite it. If the change is intentional:
    python scripts/update_api_contract.py --write --reason "why"
(the reason is recorded in docs/api.md) - and update the dashboard if it uses the changed part.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentbench.api import create_app  # noqa: E402
from agentbench.api.contract import CONTRACT_FILE, build_contract, contract_diff, load_contract  # noqa: E402
from agentbench.api.schemas import ErrorResponse  # noqa: E402
from agentbench.datasets import build_shop_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def current():
    return build_contract(create_app(":memory:").openapi())


# ---------- 1. the snapshot ---------------------------------------------------------------------------

def test_api_matches_its_pinned_contract(current):
    changes = contract_diff(load_contract(), current)
    assert changes == [], ("The API differs from its pinned contract:\n  " + "\n  ".join(changes) +
                           '\nIf intentional: python scripts/update_api_contract.py --write --reason "..."')


# ---------- 2. readable pins of what the dashboard relies on most (belt and braces) ----------------------

EXPECTED_ENDPOINTS = {
    "GET /", "GET /health", "GET /registrations", "GET /suites", "GET /suites/{suite_id}",
    "GET /suites/{suite_id}/runs/{run_id}", "GET /suites/{suite_id}/failures", "GET /tasks/{task_id}/history",
    "GET /tasks/{task_id}/measure", "GET /compare", "POST /estimates", "POST /runs", "GET /runs",
    "GET /runs/{job_id}",
}


def test_endpoints_and_methods(current):
    assert set(current["endpoints"]) == EXPECTED_ENDPOINTS                 # no PUT/PATCH/DELETE anywhere
    assert current["endpoints"]["POST /runs"]["responses"].keys() >= {"202", "403", "409", "413", "422"}
    assert current["endpoints"]["POST /runs"]["request"] == "RunIn"
    assert "query:limit:integer" in current["endpoints"]["GET /suites"]["params"]


def test_request_fields(current):
    run_in = current["schemas"]["RunIn"]
    assert run_in["fields"] == {"agent": "enum(careful,sloppy,gemini)", "suite": "string",
                                "tasks": "array[string]|null", "repeats": "integer", "budget": "integer|null",
                                "confirm": "boolean"}
    assert run_in["required"] == ["agent"]


@pytest.mark.parametrize("schema, fields", [
    ("JobOut", {"job_id": "string", "status": "string", "completed_tasks": "integer", "total_tasks": "integer",
                "percent": "number", "current_task": "null|string", "saved": "boolean|null",
                "recovery_path": "null|string", "suite_id": "null|string", "progress": "array[string]"}),
    ("SuiteSummaryOut", {"suite_id": "string", "short_id": "string", "kind": "string", "pass_rate": "RateOut",
                         "complete": "boolean", "infra_errors": "integer"}),
    ("SuitePage", {"items": "array[SuiteSummaryOut]", "pagination": "Pagination"}),
    ("Pagination", {"limit": "integer", "offset": "integer", "total": "integer", "returned": "integer",
                    "next_offset": "integer|null"}),
    ("ErrorResponse", {"error": "ErrorBody"}),
    ("ErrorBody", {"code": "string", "message": "string", "details": "any"}),
    ("EstimateOut", {"allowed": "boolean", "reasons": "array[string]", "registration": "RegistrationOut"}),
])
def test_response_fields(current, schema, fields):
    actual = current["schemas"][schema]["fields"]
    assert {k: actual.get(k) for k in fields} == fields


# ---------- 3. the contract machinery itself -------------------------------------------------------------

def test_diff_names_every_kind_of_change(current):
    changed = json.loads(json.dumps(current))
    del changed["schemas"]["JobOut"]["fields"]["percent"]
    changed["schemas"]["JobOut"]["fields"]["status"] = "integer"
    changed["schemas"]["JobOut"]["fields"]["eta"] = "number"
    del changed["endpoints"]["GET /runs"]
    changed["endpoints"]["DELETE /suites/{suite_id}"] = {"params": [], "request": None, "responses": {}}
    changes = contract_diff(current, changed)
    assert "REMOVED field JobOut.percent" in changes and "CHANGED type JobOut.status: string -> integer" in changes
    assert "added field JobOut.eta (number)" in changes and "REMOVED endpoint GET /runs" in changes
    assert "added endpoint DELETE /suites/{suite_id}" in changes


def run_script(*args, **kw):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "update_api_contract.py"), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=60, encoding="utf-8", **kw)


def test_the_update_script_never_writes_silently(tmp_path):
    stale = tmp_path / "contract.json"
    stale.write_text(json.dumps({"endpoints": {}, "schemas": {}}), encoding="utf-8")
    log = tmp_path / "api.md"
    shown = run_script("--contract-file", stale, "--changelog", log)
    assert shown.returncode == 1 and "added endpoint POST /runs" in shown.stdout     # shows, writes nothing
    no_reason = run_script("--contract-file", stale, "--changelog", log, "--write")
    assert no_reason.returncode != 0 and "needs --reason" in no_reason.stderr
    assert json.loads(stale.read_text(encoding="utf-8")) == {"endpoints": {}, "schemas": {}}   # untouched
    done = run_script("--contract-file", stale, "--changelog", log, "--write", "--reason", "test change")
    assert done.returncode == 0 and "test change" in log.read_text(encoding="utf-8")
    assert run_script("--contract-file", stale).stdout.strip() == "The API matches its pinned contract."


def test_the_committed_contract_file_is_where_the_test_reads_it():
    assert CONTRACT_FILE.exists() and load_contract()["format"] == "agentbench-api-contract/1"


# ---------- 4. status codes and the error structure, exercised for real ---------------------------------------

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("contract")
    app = create_app(tmp / "results.db", shop_db_path=build_shop_db(tmp / "shop.db"), recovery_dir=tmp / "rec",
                     real_llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no real client")),
                     sleep=lambda s: None)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("method, path, body, status, code", [
    ("GET", "/suites/zzzz9999", None, 404, "not_found"),
    ("GET", "/suites/ab", None, 422, "validation_error"),
    ("GET", "/suites?limit=0", None, 422, "validation_error"),
    ("GET", "/compare?ids=zzzz9999", None, 422, "validation_error"),
    ("GET", "/tasks/nope-1/history", None, 404, "not_found"),
    ("GET", "/runs/ffffffff", None, 404, "not_found"),
    ("GET", "/nope", None, 404, "not_found"),
    ("DELETE", "/suites/zzzz9999", None, 405, "method_not_allowed"),
    ("POST", "/runs", {"agent": "gemini", "suite": "shop-hard", "budget": 25, "confirm": True}, 403,
     "real_runs_disabled"),
    ("POST", "/runs", {"agent": "careful", "suite": "nope"}, 422, "validation_error"),
    ("POST", "/runs", {"agent": "careful", "unknown_field": 1}, 422, "validation_error"),
    ("POST", "/estimates", {"agent": "x"}, 422, "validation_error"),
])
def test_status_codes_and_error_structure(client, method, path, body, status, code):
    response = client.request(method, path, json=body)
    assert response.status_code == status, response.text
    parsed = ErrorResponse.model_validate(response.json())                    # exactly the documented shape
    assert parsed.error.code == code and parsed.error.message and set(response.json()) == {"error"}

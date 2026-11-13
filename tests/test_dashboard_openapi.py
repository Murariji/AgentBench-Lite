"""Phase 10: the dashboard's copy of the API description must match the backend exactly.

dashboard/openapi.json is the source of the dashboard's TypeScript types. If this fails, the backend's
API changed (deliberately, via scripts/update_api_contract.py) but the dashboard was not regenerated:
    python scripts/export_openapi.py      then, in dashboard/:   npm run gen:types
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_openapi import OUT, current_openapi  # noqa: E402


def test_dashboard_openapi_matches_the_backend():
    assert OUT.exists(), "run: python scripts/export_openapi.py"
    committed = json.loads(OUT.read_text(encoding="utf-8"))
    assert committed == current_openapi(), ("dashboard/openapi.json is out of date: python scripts/export_openapi.py "
                                            "then npm run gen:types in dashboard/")


def test_generated_typescript_types_exist():
    types = (ROOT / "dashboard" / "src" / "api" / "schema.d.ts").read_text(encoding="utf-8")
    for name in ("HealthOut", "SuitePage", "RunDetailOut", "JobOut", "ErrorResponse", "RunIn"):
        assert f"{name}: {{" in types, f"{name} missing from the generated types"

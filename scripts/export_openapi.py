"""Write the API's OpenAPI description to dashboard/openapi.json (the source of the dashboard's TS types).

    python scripts/export_openapi.py            # then, in dashboard/:  npm run gen:types

Read-only tooling: it builds the app in memory (no server, no database, no API calls) and writes the
same description that /openapi.json serves. tests/test_dashboard_openapi.py checks the committed copy is
current, so the dashboard's types can never silently drift from the pinned backend contract.
"""

import json
from pathlib import Path

from agentbench.api import create_app

OUT = Path(__file__).resolve().parents[1] / "dashboard" / "openapi.json"


def current_openapi() -> dict:
    return create_app(":memory:").openapi()


if __name__ == "__main__":
    OUT.write_text(json.dumps(current_openapi(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Written {OUT}")

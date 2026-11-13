"""Optional web API (Phase 9). Needs the "api" extra: pip install -e ".[dev,api]".

The core framework never imports this package, so it works without FastAPI installed.
"""

from agentbench.api.app import create_app

__all__ = ["create_app"]

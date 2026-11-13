"""The API contract (Phase 9.3): what the dashboard may rely on, pinned in contract.json.

    build_contract(app.openapi())   -> {"endpoints": {...}, "schemas": {...}}  (compact, comparable)
    contract_diff(old, new)         -> human-readable list of every difference

tests/test_api_contract.py fails when the API drifts from contract.json. Updating the snapshot is a
DELIBERATE act: `python scripts/update_api_contract.py --write --reason "..."` records the reason and the
differences in docs/api.md. Tests never rewrite it.
"""

import json
from pathlib import Path

CONTRACT_FORMAT = "agentbench-api-contract/1"
CONTRACT_FILE = Path(__file__).parent / "contract.json"


def _type(schema: dict | None) -> str:
    """One readable type string for an OpenAPI schema, e.g. 'integer', 'string|null', 'array[JobOut]'."""
    if not schema:
        return "any"
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return "|".join(sorted(_type(s) for s in schema["anyOf"]))
    if "enum" in schema:
        return "enum(" + ",".join(str(v) for v in schema["enum"]) + ")"
    kind = schema.get("type", "any")
    if kind == "array":
        return f"array[{_type(schema.get('items'))}]"
    if kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        return f"object[{_type(schema['additionalProperties'])}]"
    return kind


def build_contract(openapi: dict) -> dict:
    endpoints = {}
    for path, operations in openapi.get("paths", {}).items():
        for method, op in operations.items():
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            endpoints[f"{method.upper()} {path}"] = {
                "params": sorted(f"{p['in']}:{p['name']}:{_type(p.get('schema'))}" + ("!" if p.get("required") else "")
                                 for p in op.get("parameters", [])),
                "request": _type(body) if body else None,
                "responses": {code: _type(r.get("content", {}).get("application/json", {}).get("schema"))
                              for code, r in sorted(op.get("responses", {}).items())},
            }
    schemas = {name: {"fields": {f: _type(s) for f, s in schema.get("properties", {}).items()},
                      "required": sorted(schema.get("required", []))}
               for name, schema in sorted(openapi.get("components", {}).get("schemas", {}).items())}
    return {"format": CONTRACT_FORMAT, "endpoints": dict(sorted(endpoints.items())), "schemas": schemas}


def load_contract(path: Path = CONTRACT_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def contract_diff(old: dict, new: dict) -> list[str]:
    """Every difference between two contracts, as sentences ([] = identical)."""
    changes = []
    for kind in ("endpoints", "schemas"):
        before, after = old.get(kind, {}), new.get(kind, {})
        for name in sorted(before.keys() - after.keys()):
            changes.append(f"REMOVED {kind[:-1]} {name}")
        for name in sorted(after.keys() - before.keys()):
            changes.append(f"added {kind[:-1]} {name}")
        for name in sorted(before.keys() & after.keys()):
            a, b = before[name], after[name]
            if kind == "schemas":
                for field in sorted(a["fields"].keys() - b["fields"].keys()):
                    changes.append(f"REMOVED field {name}.{field}")
                for field in sorted(b["fields"].keys() - a["fields"].keys()):
                    changes.append(f"added field {name}.{field} ({b['fields'][field]})")
                for field in sorted(a["fields"].keys() & b["fields"].keys()):
                    if a["fields"][field] != b["fields"][field]:
                        changes.append(f"CHANGED type {name}.{field}: {a['fields'][field]} -> {b['fields'][field]}")
                if a["required"] != b["required"]:
                    changes.append(f"CHANGED required fields of {name}: {a['required']} -> {b['required']}")
            else:
                for part in ("params", "request", "responses"):
                    if a[part] != b[part]:
                        changes.append(f"CHANGED {part} of {name}: {a[part]} -> {b[part]}")
    return changes

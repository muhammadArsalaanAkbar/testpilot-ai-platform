"""Export the FastAPI app's OpenAPI schema and validate it covers every
endpoint documented in contracts/*.md (T200, plan.md API Design).

Usage:
    python scripts/export_openapi.py [output_path]

Exit code is non-zero if any non-Future contract endpoint is missing from
the generated schema — this is meant to run in CI (Phase 24) as a build-time
guard against the implementation silently drifting from the contracts, the
same spirit as T201's contract-coverage test but checking route
*existence* rather than test coverage.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
CONTRACTS_DIR = REPO_ROOT / "specs" / "001-testpilot-ai-platform" / "contracts"
DEFAULT_OUTPUT = BACKEND_ROOT / "openapi.json"
API_PREFIX = "/api/v1"

_ROW_RE = re.compile(r"^\|\s*`(GET|POST|PATCH|PUT|DELETE)\s+([^`]+)`\s*(.*)\|")
_PARAM_RE = re.compile(r"\{[^}/]+\}")


def _normalize(path: str) -> str:
    """Path-parameter names differ between contracts' shorthand (`{id}`)
    and the real routes' specific names (`{project_id}`) -- every `{...}`
    segment is collapsed to a single placeholder so the two sides compare
    on structure only."""
    return _PARAM_RE.sub("{}", path.rstrip("/"))


def documented_endpoints() -> dict[tuple[str, str], bool]:
    """Returns {(method, normalized_path): is_future} for every endpoint
    row across every contracts/*.md file except _conventions.md, which
    documents cross-cutting rules rather than endpoints."""
    endpoints: dict[tuple[str, str], bool] = {}
    for contract_file in sorted(CONTRACTS_DIR.glob("*.md")):
        if contract_file.name == "_conventions.md":
            continue
        for line in contract_file.read_text(encoding="utf-8").splitlines():
            match = _ROW_RE.match(line)
            if not match:
                continue
            method, raw_path, rest = match.groups()
            is_future = "(Future)" in raw_path or "(Future)" in rest
            path = API_PREFIX + _normalize(raw_path.strip())
            endpoints[(method, path)] = is_future
    return endpoints


def schema_endpoints(schema: dict[str, Any]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path, methods in schema.get("paths", {}).items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                found.add((method.upper(), _normalize(path)))
    return found


def export(output_path: Path) -> dict[str, Any]:
    from testpilot.api.main import app

    schema: dict[str, Any] = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return schema


def validate(schema: dict[str, Any]) -> list[tuple[str, str]]:
    """Returns the list of non-Future (method, path) pairs documented in
    contracts/*.md that have no matching route in the generated schema."""
    in_schema = schema_endpoints(schema)
    missing = []
    for (method, path), is_future in documented_endpoints().items():
        if is_future:
            continue
        if (method, path) not in in_schema:
            missing.append((method, path))
    return sorted(missing)


def main() -> int:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    schema = export(output_path)
    missing = validate(schema)

    if missing:
        print(f"OpenAPI schema is missing {len(missing)} contract-documented endpoint(s):")
        for method, path in missing:
            print(f"  {method} {path}")
        return 1

    print(f"OpenAPI schema exported to {output_path} ({len(schema.get('paths', {}))} paths).")
    print("Every non-Future contracts/*.md endpoint has a matching route.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

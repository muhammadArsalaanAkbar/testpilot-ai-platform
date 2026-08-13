"""Contract-coverage audit (T201, constitution's Integration Testing
principle): every non-Future endpoint documented in contracts/*.md must
have at least one passing contract test that actually calls it.

Static analysis over tests/contract/*.py's `client.<method>(...)` call
sites (this file excluded) rather than live HTTP-traffic recording — the
established `client` fixture is function-scoped and recreated per test, and
this codebase's contract tests overwhelmingly use inline f-string paths
(`client.get(f"/projects/{project_id}/issues", ...)`), which normalizes
cleanly against contracts/*.md's own `{id}`-style shorthand the same way
scripts/export_openapi.py's `documented_endpoints()` does — reused here
directly rather than re-implemented.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from export_openapi import documented_endpoints  # noqa: E402

CONTRACT_TESTS_DIR = Path(__file__).resolve().parent
API_PREFIX = "/api/v1"

_METHOD_CALL_RE = re.compile(r'client\.(get|post|patch|put|delete)\(\s*f?"([^"]*)"')
# httpx has no client.delete(..., json=...) — a DELETE with a request body
# (contracts/projects-api.md's `{confirm: true}` hard-delete) goes through
# the low-level client.request("DELETE", ...) instead.
_REQUEST_CALL_RE = re.compile(r'client\.request\(\s*"(GET|POST|PATCH|PUT|DELETE)"\s*,\s*f?"([^"]*)"')
_PARAM_RE = re.compile(r"\{[^}/]+\}")
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_METHOD_MAP = {"get": "GET", "post": "POST", "patch": "PATCH", "put": "PUT", "delete": "DELETE"}


def _normalize(path: str) -> str:
    path = path.split("?", 1)[0].rstrip("/")
    path = _UUID_RE.sub("{}", path)
    return _PARAM_RE.sub("{}", path)


def _tested_endpoints() -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for test_file in CONTRACT_TESTS_DIR.glob("test_*.py"):
        if test_file.name == "test_contract_coverage.py":
            continue
        source = test_file.read_text(encoding="utf-8")
        for method_group, raw_path in _METHOD_CALL_RE.findall(source):
            path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
            endpoints.add((_METHOD_MAP[method_group], API_PREFIX + _normalize(path)))
        for method, raw_path in _REQUEST_CALL_RE.findall(source):
            path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
            endpoints.add((method, API_PREFIX + _normalize(path)))
    return endpoints


def test_every_non_future_contract_endpoint_has_a_contract_test():
    documented = documented_endpoints()
    tested = _tested_endpoints()

    missing = sorted(
        (method, path) for (method, path), is_future in documented.items() if not is_future and (method, path) not in tested
    )

    assert missing == [], (
        f"{len(missing)} contracts/*.md endpoint(s) have no contract test calling them:\n"
        + "\n".join(f"  {method} {path}" for method, path in missing)
    )


def test_coverage_audit_itself_finds_a_real_gap_when_one_exists():
    """A test for the auditor: an endpoint absent from `tested` must be
    reported, proving `missing` isn't vacuously empty by construction."""
    documented = {("GET", "/api/v1/definitely/not/a/real/endpoint"): False}
    tested = _tested_endpoints()
    missing = [(m, p) for (m, p), is_future in documented.items() if not is_future and (m, p) not in tested]
    assert missing == [("GET", "/api/v1/definitely/not/a/real/endpoint")]

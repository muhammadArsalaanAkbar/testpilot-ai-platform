"""Unit tests for scripts/export_openapi.py (T200): the documented-vs-schema
comparison logic, and a real regression guard confirming the actual app's
generated schema covers every non-Future contracts/*.md endpoint today."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from export_openapi import documented_endpoints, schema_endpoints, validate  # noqa: E402


def test_documented_endpoints_finds_rows_across_multiple_contract_files():
    endpoints = documented_endpoints()
    assert ("POST", "/api/v1/auth/signup") in endpoints
    assert ("GET", "/api/v1/projects") in endpoints
    assert ("POST", "/api/v1/projects/{}/issues") in endpoints


def test_documented_endpoints_flags_future_rows():
    endpoints = documented_endpoints()
    assert endpoints[("GET", "/api/v1/projects/{}/reports/trend")] is True
    assert endpoints[("POST", "/api/v1/auth/signup")] is False


def test_documented_endpoints_skips_conventions_file():
    """_conventions.md has no `METHOD /path` table rows of its own (it
    documents cross-cutting rules) -- nothing from it should leak in."""
    endpoints = documented_endpoints()
    assert all(path.startswith("/api/v1/") for _method, path in endpoints)


def test_schema_endpoints_normalizes_path_parameter_names():
    schema = {"paths": {"/api/v1/projects/{project_id}": {"get": {}, "patch": {}}}}
    assert schema_endpoints(schema) == {("GET", "/api/v1/projects/{}"), ("PATCH", "/api/v1/projects/{}")}


def test_validate_reports_a_documented_endpoint_missing_from_the_schema():
    schema = {"paths": {}}
    missing = validate(schema)
    assert ("POST", "/api/v1/auth/signup") in missing


def test_validate_ignores_future_endpoints_missing_from_the_schema():
    schema = {"paths": {}}
    missing = validate(schema)
    assert ("GET", "/api/v1/projects/{}/reports/trend") not in missing


def test_the_real_app_schema_covers_every_non_future_contract_endpoint():
    """Regression guard: if a route is ever renamed/removed without
    updating its contract (or vice versa), this fails."""
    from testpilot.api.main import app

    schema = app.openapi()
    missing = validate(schema)
    assert missing == []

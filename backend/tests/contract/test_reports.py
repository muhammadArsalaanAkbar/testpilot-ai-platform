"""Contract tests for the Reports & Analytics API (T182, contracts/reports-api.md):
summary, issues-by-severity, run-history, and the Future trend/rollup stubs.

Report data is seeded directly via the ORM (session_scope) rather than driving
a real browser execution for every run/result — the same established pattern
as tests/unit/cli/test_billing_cli.py's `_create_organization` — because this
test's target is the aggregation/read logic in reports/service.py, not the
execution engine (already covered by tests/contract/test_ai_analysis.py etc).
Every row is still real, persisted, RLS-scoped data, not a mock.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from testpilot.core.db import session_scope
from testpilot.execution.models import TestResult, TestResultStatus, TestRun
from testpilot.issues.models import Issue, IssuePriority, IssueSeverity
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
)

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="reports-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Reports Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Reports Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _make_test_case(
    *, organization_id: str, project_id: str, status: TestCaseStatus, title: str = "Case"
) -> uuid.UUID:
    async with session_scope(organization_id=organization_id) as session:
        case = TestCase(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            title=title,
            description="A test case.",
            priority=TestCasePriority.medium,
            severity=TestCaseSeverity.major,
            status=status,
            source=TestCaseSource.manual,
        )
        session.add(case)
        await session.flush()
        return case.id


async def _make_test_run(
    *,
    organization_id: str,
    project_id: str,
    user_id: str,
    summary_total: int,
    summary_passed: int,
    summary_failed: int,
    summary_skipped: int,
    created_at: datetime,
) -> uuid.UUID:
    async with session_scope(organization_id=organization_id) as session:
        run = TestRun(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            initiated_by_user_id=uuid.UUID(user_id),
            summary_total=summary_total,
            summary_passed=summary_passed,
            summary_failed=summary_failed,
            summary_skipped=summary_skipped,
            created_at=created_at,
        )
        session.add(run)
        await session.flush()
        return run.id


async def _make_test_result(
    *,
    organization_id: str,
    test_run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    status: TestResultStatus,
    completed_at: datetime,
) -> None:
    async with session_scope(organization_id=organization_id) as session:
        session.add(
            TestResult(
                organization_id=uuid.UUID(organization_id),
                test_run_id=test_run_id,
                test_case_id=test_case_id,
                status=status,
                started_at=completed_at,
                completed_at=completed_at,
                duration_ms=1000,
            )
        )


async def _make_issue(
    *, organization_id: str, project_id: str, user_id: str, severity: IssueSeverity, created_at: datetime
) -> None:
    async with session_scope(organization_id=organization_id) as session:
        issue = Issue(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            title="Something broke",
            description="Details.",
            severity=severity,
            priority=IssuePriority.medium,
            created_by_user_id=uuid.UUID(user_id),
        )
        session.add(issue)
        await session.flush()
        issue.created_at = created_at
        session.add(issue)


async def _seed_report_fixture(client, token, organization_id, user_id, project_id):
    """3 approved cases + 1 draft case; a run covering 2 of the 3 approved
    cases (1 passed, 1 failed); the third approved case has no result at
    all (uncovered) — coverage_percentage MUST be 2/3, never 2/4 (the draft
    case is excluded from the denominator, FR-105)."""
    now = datetime.now(UTC)

    case_a = await _make_test_case(organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Case A")
    case_b = await _make_test_case(organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Case B")
    await _make_test_case(organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Case C (uncovered)")
    await _make_test_case(organization_id=organization_id, project_id=project_id, status=TestCaseStatus.draft, title="Draft case")

    run_id = await _make_test_run(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user_id,
        summary_total=2,
        summary_passed=1,
        summary_failed=1,
        summary_skipped=0,
        created_at=now,
    )
    await _make_test_result(
        organization_id=organization_id, test_run_id=run_id, test_case_id=case_a, status=TestResultStatus.passed, completed_at=now
    )
    await _make_test_result(
        organization_id=organization_id, test_run_id=run_id, test_case_id=case_b, status=TestResultStatus.failed, completed_at=now
    )

    await _make_issue(organization_id=organization_id, project_id=project_id, user_id=user_id, severity=IssueSeverity.minor, created_at=now)
    await _make_issue(organization_id=organization_id, project_id=project_id, user_id=user_id, severity=IssueSeverity.minor, created_at=now)
    await _make_issue(organization_id=organization_id, project_id=project_id, user_id=user_id, severity=IssueSeverity.critical, created_at=now)

    return run_id


async def test_summary_matches_seeded_runs_and_coverage(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await _seed_report_fixture(client, token, organization_id, user_id, project_id)

    response = await client.get(f"/projects/{project_id}/reports/summary", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["passed"] == 1
    assert body["failed"] == 1
    assert body["skipped"] == 0
    assert body["pass_percentage"] == pytest.approx(50.0)
    assert body["failure_percentage"] == pytest.approx(50.0)
    assert body["coverage_percentage"] == pytest.approx(2 / 3 * 100)


async def test_summary_returns_404_for_a_nonexistent_project(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.get(f"/projects/{uuid.uuid4()}/reports/summary", headers=_auth_headers(token))
    assert response.status_code == 404


async def test_summary_requires_authentication(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    response = await client.get(f"/projects/{project_id}/reports/summary")
    assert response.status_code == 401


async def test_summary_excludes_runs_outside_the_requested_range(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    old = datetime.now(UTC) - timedelta(days=90)
    await _make_test_run(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user_id,
        summary_total=5,
        summary_passed=5,
        summary_failed=0,
        summary_skipped=0,
        created_at=old,
    )

    response = await client.get(f"/projects/{project_id}/reports/summary", headers=_auth_headers(token))
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_issues_by_severity_matches_seeded_issues(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await _seed_report_fixture(client, token, organization_id, user_id, project_id)

    response = await client.get(f"/projects/{project_id}/reports/issues-by-severity", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body == {"minor": 2, "major": 0, "critical": 1, "blocker": 0}


async def test_issues_by_severity_returns_404_for_a_nonexistent_project(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.get(f"/projects/{uuid.uuid4()}/reports/issues-by-severity", headers=_auth_headers(token))
    assert response.status_code == 404


async def test_run_history_lists_seeded_runs_newest_first(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    first_run_id = await _seed_report_fixture(client, token, organization_id, user_id, project_id)
    second_run_id = await _make_test_run(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user_id,
        summary_total=1,
        summary_passed=1,
        summary_failed=0,
        summary_skipped=0,
        created_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    response = await client.get(f"/projects/{project_id}/reports/run-history", headers=_auth_headers(token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["id"] == str(second_run_id)
    assert items[1]["id"] == str(first_run_id)


async def test_run_history_returns_404_for_a_nonexistent_project(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.get(f"/projects/{uuid.uuid4()}/reports/run-history", headers=_auth_headers(token))
    assert response.status_code == 404


async def test_trend_is_not_implemented_yet(client):
    """T188: schema-free Future stub (FR-108)."""
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    response = await client.get(f"/projects/{project_id}/reports/trend", headers=_auth_headers(token))
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


async def test_organization_rollup_is_not_implemented_yet(client):
    """T188: Future stub (FR-111)."""
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.get("/organizations/current/reports/rollup", headers=_auth_headers(token))
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"

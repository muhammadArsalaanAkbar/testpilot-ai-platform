"""Integration test: `coverage_percentage` is computed correctly against
approved-versus-executed cases (T183, FR-105). Complements
tests/contract/test_reports.py's happy-path contract assertions with the
edge cases that make the denominator/numerator selection non-trivial:
rejected/draft cases never count, a result outside the requested range
doesn't count as "covered", and a case's *current* status (not its status
at execution time) decides whether it belongs in the denominator at all.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from testpilot.core.db import session_scope
from testpilot.execution.models import TestResult, TestResultStatus, TestRun
from testpilot.reports import service
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
)

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="reports-coverage@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Coverage Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Coverage Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _make_test_case(
    *, organization_id: str, project_id: str, status: TestCaseStatus, title: str
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


async def _make_run_and_result(
    *, organization_id: str, project_id: str, user_id: str, test_case_id: uuid.UUID, completed_at: datetime
) -> None:
    async with session_scope(organization_id=organization_id) as session:
        run = TestRun(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            initiated_by_user_id=uuid.UUID(user_id),
            summary_total=1,
            summary_passed=1,
            summary_failed=0,
            summary_skipped=0,
            created_at=completed_at,
        )
        session.add(run)
        await session.flush()
        session.add(
            TestResult(
                organization_id=uuid.UUID(organization_id),
                test_run_id=run.id,
                test_case_id=test_case_id,
                status=TestResultStatus.passed,
                started_at=completed_at,
                completed_at=completed_at,
                duration_ms=500,
            )
        )


async def test_coverage_excludes_rejected_and_draft_cases_from_the_denominator(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    now = datetime.now(UTC)

    approved_and_run = await _make_test_case(
        organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Approved, run"
    )
    await _make_test_case(
        organization_id=organization_id, project_id=project_id, status=TestCaseStatus.rejected, title="Rejected"
    )
    await _make_test_case(
        organization_id=organization_id, project_id=project_id, status=TestCaseStatus.draft, title="Draft"
    )
    await _make_run_and_result(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user_id,
        test_case_id=approved_and_run,
        completed_at=now,
    )

    summary = await service.get_summary(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), from_date=None, to_date=None
    )

    # Only one approved case exists; it was run once -> 100%, not 1/3.
    assert summary.coverage_percentage == pytest.approx(100.0)


async def test_coverage_ignores_a_result_outside_the_requested_range(client):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    old = datetime.now(UTC) - timedelta(days=60)

    case_id = await _make_test_case(
        organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Approved, run long ago"
    )
    await _make_run_and_result(
        organization_id=organization_id, project_id=project_id, user_id=user_id, test_case_id=case_id, completed_at=old
    )

    # Default range is the last 30 days; a 60-day-old result must not count.
    summary = await service.get_summary(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), from_date=None, to_date=None
    )

    assert summary.coverage_percentage == pytest.approx(0.0)

    # But it MUST count once the requested range actually covers it.
    summary_in_range = await service.get_summary(
        organization_id=uuid.UUID(organization_id),
        project_id=uuid.UUID(project_id),
        from_date=(old - timedelta(days=1)).date(),
        to_date=datetime.now(UTC).date(),
    )
    assert summary_in_range.coverage_percentage == pytest.approx(100.0)


async def test_coverage_reflects_a_cases_current_status_not_its_status_when_executed(client):
    """A case approved and executed, then later edited back to draft
    (data-model.md: `approved -> ... -> draft` re-edit transition), must
    drop out of both the numerator and denominator — coverage reflects the
    Organization's current approved set, not a historical snapshot."""
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    now = datetime.now(UTC)

    case_id = await _make_test_case(
        organization_id=organization_id, project_id=project_id, status=TestCaseStatus.approved, title="Later un-approved"
    )
    await _make_run_and_result(
        organization_id=organization_id, project_id=project_id, user_id=user_id, test_case_id=case_id, completed_at=now
    )

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(TestCase).where(TestCase.id == case_id))
        case = result.scalar_one()
        case.status = TestCaseStatus.draft
        session.add(case)

    summary = await service.get_summary(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), from_date=None, to_date=None
    )

    # No approved cases remain -> percentage is 0, not division-by-zero-as-100.
    assert summary.coverage_percentage == pytest.approx(0.0)

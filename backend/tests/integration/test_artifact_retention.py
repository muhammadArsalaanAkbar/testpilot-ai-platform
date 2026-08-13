"""Integration test: the artifact retention/purge job (T153, DATA-003).

Exercises the real `S3ArtifactStorage` adapter against local MinIO and the
real `purge_expired_artifacts` job function directly — the same function a
scheduler would invoke via `worker/jobs/purge_artifacts.py`'s `handle`, not
a fake/mocked storage or a simulated purge.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from testpilot.core.config import get_settings
from testpilot.core.db import session_scope
from testpilot.execution.artifact_models import Artifact, ArtifactType
from testpilot.storage.base import ArtifactNotFoundError
from testpilot.storage.s3 import S3ArtifactStorage
from testpilot.worker.jobs.purge_artifacts import purge_expired_artifacts

pytestmark = pytest.mark.anyio


def _storage() -> S3ArtifactStorage:
    settings = get_settings()
    return S3ArtifactStorage(
        endpoint_url=settings.object_storage_endpoint_url,
        bucket=settings.object_storage_bucket,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        region=settings.object_storage_region,
    )


async def _signup(client, email):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Retention Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


async def _create_project_and_case(client, token):
    project = await client.post(
        "/projects", json={"name": "Retention Project", "url": "https://example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = project.json()["id"]
    case = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "C", "description": "D", "priority": "low", "severity": "minor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return project_id, case.json()["id"]


async def _seed_artifact(
    *, organization_id: str, test_result_id: uuid.UUID, storage_key: str, captured_at: datetime
) -> uuid.UUID:
    async with session_scope(organization_id=organization_id) as session:
        artifact = Artifact(
            organization_id=uuid.UUID(organization_id),
            test_result_id=test_result_id,
            type=ArtifactType.screenshot,
            storage_key=storage_key,
            content_type="image/png",
            size_bytes=10,
            captured_at=captured_at,
        )
        session.add(artifact)
        await session.flush()
        await session.refresh(artifact)
        return artifact.id


async def _seed_test_result(*, organization_id: str, project_id: str, test_case_id: str, user_id: str) -> uuid.UUID:
    """Artifacts FK to test_results, which FK to test_runs — minimal real
    rows for both (not a full executed run) are enough scaffolding for a
    storage-focused retention test."""
    from testpilot.execution.models import TestResult, TestResultStatus, TestRun, TestRunStatus

    async with session_scope(organization_id=organization_id) as session:
        run = TestRun(
            organization_id=uuid.UUID(organization_id),
            project_id=uuid.UUID(project_id),
            initiated_by_user_id=uuid.UUID(user_id),
            status=TestRunStatus.completed,
            summary_total=1,
            summary_failed=1,
        )
        session.add(run)
        await session.flush()

        result = TestResult(
            organization_id=uuid.UUID(organization_id),
            test_run_id=run.id,
            test_case_id=uuid.UUID(test_case_id),
            status=TestResultStatus.failed,
            execution_log=[],
            failure_step_index=0,
            error_message="seeded for retention test",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=100,
        )
        session.add(result)
        await session.flush()
        await session.refresh(result)
        return result.id


async def test_purge_nulls_storage_key_and_deletes_the_object_past_the_retention_window(client):
    token, organization_id, user_id = await _signup(client, "retention-old@example.com")
    project_id, case_id = await _create_project_and_case(client, token)
    test_result_id = await _seed_test_result(organization_id=organization_id, project_id=project_id, test_case_id=case_id, user_id=user_id)

    storage = _storage()
    storage_key = await storage.put(b"old screenshot", content_type="image/png")
    old_captured_at = datetime.now(UTC) - timedelta(days=200)
    artifact_id = await _seed_artifact(
        organization_id=organization_id, test_result_id=test_result_id, storage_key=storage_key, captured_at=old_captured_at
    )

    purged_count = await purge_expired_artifacts(storage=storage, retention_days=90)

    assert purged_count >= 1
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_id))
        artifact = result.scalar_one()
        assert artifact.storage_key is None

    with pytest.raises(ArtifactNotFoundError):
        await storage.get_url(storage_key, expires_in=60)


async def test_purge_does_not_touch_artifacts_within_the_retention_window(client):
    """Critical boundary: a recent artifact must survive a purge run
    untouched, both in the DB and in physical storage."""
    token, organization_id, user_id = await _signup(client, "retention-recent@example.com")
    project_id, case_id = await _create_project_and_case(client, token)
    test_result_id = await _seed_test_result(organization_id=organization_id, project_id=project_id, test_case_id=case_id, user_id=user_id)

    storage = _storage()
    storage_key = await storage.put(b"recent screenshot", content_type="image/png")
    recent_captured_at = datetime.now(UTC) - timedelta(days=1)
    artifact_id = await _seed_artifact(
        organization_id=organization_id, test_result_id=test_result_id, storage_key=storage_key, captured_at=recent_captured_at
    )

    await purge_expired_artifacts(storage=storage, retention_days=90)

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_id))
        artifact = result.scalar_one()
        assert artifact.storage_key == storage_key

    url = await storage.get_url(storage_key, expires_in=60)
    assert url.startswith("http")


async def test_purge_preserves_the_test_results_outcome_and_metadata(client):
    """DATA-003: expiry must not delete the parent TestResult's pass/fail
    outcome or metadata, only the binary artifact."""
    token, organization_id, user_id = await _signup(client, "retention-outcome@example.com")
    project_id, case_id = await _create_project_and_case(client, token)
    test_result_id = await _seed_test_result(organization_id=organization_id, project_id=project_id, test_case_id=case_id, user_id=user_id)

    storage = _storage()
    storage_key = await storage.put(b"expiring", content_type="image/png")
    await _seed_artifact(
        organization_id=organization_id,
        test_result_id=test_result_id,
        storage_key=storage_key,
        captured_at=datetime.now(UTC) - timedelta(days=200),
    )

    await purge_expired_artifacts(storage=storage, retention_days=90)

    from testpilot.execution.models import TestResult, TestResultStatus

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(TestResult).where(TestResult.id == test_result_id))
        test_result = result.scalar_one()
        assert test_result.status == TestResultStatus.failed
        assert test_result.error_message == "seeded for retention test"
        assert test_result.duration_ms == 100


async def test_purge_is_a_no_op_the_second_time_it_runs(client):
    """Idempotent: an already-purged artifact (storage_key already null)
    must not be re-processed or cause an error on a subsequent run."""
    token, organization_id, user_id = await _signup(client, "retention-idempotent@example.com")
    project_id, case_id = await _create_project_and_case(client, token)
    test_result_id = await _seed_test_result(organization_id=organization_id, project_id=project_id, test_case_id=case_id, user_id=user_id)

    storage = _storage()
    storage_key = await storage.put(b"old", content_type="image/png")
    await _seed_artifact(
        organization_id=organization_id,
        test_result_id=test_result_id,
        storage_key=storage_key,
        captured_at=datetime.now(UTC) - timedelta(days=200),
    )

    first_count = await purge_expired_artifacts(storage=storage, retention_days=90)
    second_count = await purge_expired_artifacts(storage=storage, retention_days=90)

    assert first_count >= 1
    assert second_count == 0


async def test_purge_across_multiple_organizations_only_affects_each_ones_own_artifacts(client):
    """The job runs across every Organization (it is not itself an
    RLS-scoped request), but each purge decision must stay correctly scoped
    — Organization A's expired artifact must never affect Organization B's
    recent one."""
    token_a, org_a, user_a = await _signup(client, "retention-multi-a@example.com")
    project_a, case_a = await _create_project_and_case(client, token_a)
    result_a = await _seed_test_result(organization_id=org_a, project_id=project_a, test_case_id=case_a, user_id=user_a)

    token_b, org_b, user_b = await _signup(client, "retention-multi-b@example.com")
    project_b, case_b = await _create_project_and_case(client, token_b)
    result_b = await _seed_test_result(organization_id=org_b, project_id=project_b, test_case_id=case_b, user_id=user_b)

    storage = _storage()
    old_key = await storage.put(b"org a old", content_type="image/png")
    recent_key = await storage.put(b"org b recent", content_type="image/png")
    artifact_a = await _seed_artifact(
        organization_id=org_a, test_result_id=result_a, storage_key=old_key,
        captured_at=datetime.now(UTC) - timedelta(days=200),
    )
    artifact_b = await _seed_artifact(
        organization_id=org_b, test_result_id=result_b, storage_key=recent_key,
        captured_at=datetime.now(UTC) - timedelta(days=1),
    )

    await purge_expired_artifacts(storage=storage, retention_days=90)

    async with session_scope(organization_id=org_a) as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_a))
        assert result.scalar_one().storage_key is None

    async with session_scope(organization_id=org_b) as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_b))
        assert result.scalar_one().storage_key == recent_key

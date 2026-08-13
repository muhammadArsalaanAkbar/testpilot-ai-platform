"""Artifact retention/purge job (T153, DATA-003, plan.md Screenshot &
Artifact Storage Architecture).

Not queue-driven like the other worker jobs (contracts/worker-jobs.md's
three queues are all per-resource async jobs triggered by a user action;
this is a scheduled maintenance sweep with no triggering request) — invoked
directly, e.g. by an external cron calling `handle()`.

Runs across every Organization rather than being scoped to one, since
retention applies platform-wide. This does NOT bypass RLS: `organizations`
itself is not Organization-scoped (it *is* the scope — orgs/models.py), so
listing every org's id needs no RLS context; the actual purge work for each
org still runs inside that org's own `session_scope(organization_id=...)`,
identical to every other RLS-respecting query in this codebase. Nothing
here uses an elevated/admin connection.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from testpilot.core.config import get_settings
from testpilot.core.db import dispose_engine, session_scope
from testpilot.execution.artifact_models import Artifact
from testpilot.orgs.models import Organization
from testpilot.storage import get_storage
from testpilot.storage.base import ArtifactStorage


def handle() -> None:
    asyncio.run(_handle_async())


async def _handle_async() -> None:
    try:
        await purge_expired_artifacts(storage=get_storage())
    finally:
        await dispose_engine()


async def purge_expired_artifacts(*, storage: ArtifactStorage, retention_days: int | None = None) -> int:
    """Nulls `storage_key` (and deletes the underlying object) for every
    artifact captured before the retention window, across every
    Organization. Returns the number of artifacts purged. The parent
    `TestResult` row — its pass/fail outcome, execution log, timestamps —
    is never touched (DATA-003).
    """
    if retention_days is None:
        retention_days = get_settings().artifact_retention_days
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    async with session_scope() as session:
        org_ids_result = await session.execute(select(Organization.id))
        org_ids = list(org_ids_result.scalars().all())

    total_purged = 0
    for org_id in org_ids:
        total_purged += await _purge_for_organization(organization_id=org_id, cutoff=cutoff, storage=storage)
    return total_purged


async def _purge_for_organization(*, organization_id: uuid.UUID, cutoff: datetime, storage: ArtifactStorage) -> int:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Artifact).where(
                Artifact.organization_id == organization_id,
                Artifact.storage_key.is_not(None),
                Artifact.captured_at < cutoff,
            )
        )
        artifacts = list(result.scalars().all())

        purged = 0
        for artifact in artifacts:
            storage_key = artifact.storage_key
            assert storage_key is not None  # guaranteed by the query filter above
            try:
                await storage.delete(storage_key)
            except Exception:  # noqa: BLE001
                # Physical delete failed (e.g. transient storage outage) —
                # leave storage_key intact so this artifact is retried on
                # the next scheduled run, rather than nulling the DB
                # reference while the object may still physically exist
                # (would leave DB metadata and storage inconsistent).
                continue
            artifact.storage_key = None
            session.add(artifact)
            purged += 1
        return purged

"""Notifications business logic (data-model.md `notifications`, T191, FR-112-FR-116).

Notifications are written synchronously by whichever process completes the
triggering event, directly into this table (plan.md's Notifications
Architecture) — `create_notification` takes an already-open `AsyncSession`
so the write commits atomically with the caller's own row (the `TestRun`
status update, the `AIAnalysis` row) rather than needing its own
transaction. See execution/runner.py and ai_analysis/service.py for the
actual trigger call sites (T192).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.core.db import session_scope
from testpilot.core.exceptions import NotFoundError
from testpilot.execution.models import TestResult, TestRun
from testpilot.notifications.models import Notification, NotificationType


async def create_notification(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    type: NotificationType,
    related_entity_type: str,
    related_entity_id: uuid.UUID,
) -> Notification:
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    session.add(notification)
    return notification


@dataclass(frozen=True)
class NotificationContext:
    """Resolved routing context (contracts/notifications-api.md: "the
    frontend resolves related_entity_type/related_entity_id into a route
    ... using a small client-side lookup table") — the persisted row has
    no project_id/test_run_id column (data-model.md), so this is computed
    at read time via the entity's own current parent chain, additive to
    the documented Notification object shape, never stored redundantly."""

    project_id: uuid.UUID | None
    test_run_id: uuid.UUID | None


async def _resolve_context(
    session: AsyncSession, *, organization_id: uuid.UUID, related_entity_type: str, related_entity_id: uuid.UUID
) -> NotificationContext:
    if related_entity_type == "test_run":
        result = await session.execute(
            select(TestRun.project_id).where(
                TestRun.id == related_entity_id, TestRun.organization_id == organization_id
            )
        )
        project_id = result.scalar_one_or_none()
        return NotificationContext(project_id=project_id, test_run_id=related_entity_id if project_id else None)

    if related_entity_type == "test_result":
        result = await session.execute(
            select(TestRun.project_id, TestRun.id)
            .select_from(TestResult)
            .join(TestRun, TestRun.id == TestResult.test_run_id)
            .where(TestResult.id == related_entity_id, TestResult.organization_id == organization_id)
        )
        row = result.one_or_none()
        if row is None:
            return NotificationContext(project_id=None, test_run_id=None)
        project_id, test_run_id = row
        return NotificationContext(project_id=project_id, test_run_id=test_run_id)

    return NotificationContext(project_id=None, test_run_id=None)


async def get_notification_context(
    *, organization_id: uuid.UUID, related_entity_type: str, related_entity_id: uuid.UUID
) -> NotificationContext:
    """Public single-notification variant of `_resolve_context`, for the
    route layer's mark-read response (which needs one notification's
    context, not a whole list)."""
    async with session_scope(organization_id=str(organization_id)) as session:
        return await _resolve_context(
            session,
            organization_id=organization_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    return NotificationContext(project_id=None, test_run_id=None)


@dataclass(frozen=True)
class NotificationWithContext:
    notification: Notification
    context: NotificationContext


async def list_notifications(
    *, organization_id: uuid.UUID, user_id: uuid.UUID, unread_only: bool = False, page: int = 1, page_size: int = 25
) -> tuple[list[NotificationWithContext], int]:
    async with session_scope(organization_id=str(organization_id)) as session:
        base_filters = [Notification.organization_id == organization_id, Notification.user_id == user_id]

        unread_count_result = await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(*base_filters, Notification.read_at.is_(None))
        )
        unread_count = unread_count_result.scalar_one()

        filters = [*base_filters, Notification.read_at.is_(None)] if unread_only else base_filters
        result = await session.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        notifications = list(result.scalars().all())

        items = [
            NotificationWithContext(
                notification=notification,
                context=await _resolve_context(
                    session,
                    organization_id=organization_id,
                    related_entity_type=notification.related_entity_type,
                    related_entity_id=notification.related_entity_id,
                ),
            )
            for notification in notifications
        ]

    return items, unread_count


async def _get_notification_or_404(
    session: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification not found")
    return notification


async def mark_read(*, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    """Idempotent (contracts/notifications-api.md) — re-marking an
    already-read notification leaves its original `read_at` untouched."""
    async with session_scope(organization_id=str(organization_id)) as session:
        notification = await _get_notification_or_404(
            session, organization_id=organization_id, user_id=user_id, notification_id=notification_id
        )
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            session.add(notification)
        await session.flush()
        return notification


async def mark_all_read(*, organization_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(Notification).where(
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        for notification in result.scalars().all():
            notification.read_at = now
            session.add(notification)

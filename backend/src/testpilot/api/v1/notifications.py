"""Notifications routes (contracts/notifications-api.md, T193)."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.api.pagination import PaginationParams
from testpilot.notifications import service
from testpilot.notifications.models import Notification
from testpilot.notifications.schemas import (
    MarkReadResponse,
    NotificationListResponse,
    NotificationPublic,
)
from testpilot.notifications.service import NotificationContext

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_public(notification: Notification, context: NotificationContext) -> NotificationPublic:
    return NotificationPublic(
        id=notification.id,
        type=notification.type,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
        project_id=context.project_id,
        test_run_id=context.test_run_id,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    pagination: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationListResponse:
    items, unread_count = await service.list_notifications(
        organization_id=uuid.UUID(current_user.organization_id),
        user_id=uuid.UUID(current_user.user_id),
        unread_only=unread_only,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return NotificationListResponse(
        items=[_to_public(item.notification, item.context) for item in items], unread_count=unread_count
    )


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)
) -> MarkReadResponse:
    organization_id = uuid.UUID(current_user.organization_id)
    notification = await service.mark_read(
        organization_id=organization_id, user_id=uuid.UUID(current_user.user_id), notification_id=notification_id
    )
    context = await service.get_notification_context(
        organization_id=organization_id,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
    )
    return MarkReadResponse(notification=_to_public(notification, context))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(current_user: CurrentUser = Depends(get_current_user)) -> None:
    await service.mark_all_read(
        organization_id=uuid.UUID(current_user.organization_id), user_id=uuid.UUID(current_user.user_id)
    )

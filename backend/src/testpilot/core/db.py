from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from testpilot.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _session_factory


async def set_rls_context(
    session: AsyncSession, *, organization_id: str | None = None, user_id: str | None = None
) -> None:
    """Sets the Postgres session variables RLS policies read from
    (`app.current_org_id`, `app.current_user_id`) for the remainder of the
    session's current transaction.

    Exposed separately from `session_scope` (which calls this once up
    front) because some flows don't know the relevant id(s) until partway
    through the transaction — signup is the canonical example: the new
    User and Organization don't exist yet when the session opens, but the
    `memberships` RLS policy requires `app.current_user_id` to already
    equal the new user's id before the INSERT of their owner Membership row
    is permitted (see the rls migration's `WITH CHECK`-via-`USING` semantics).
    Call this again mid-transaction once those ids are known.

    `set_config(..., is_local=true)` is used instead of `SET LOCAL` directly
    because asyncpg does not support bind parameters inside a SET statement;
    set_config is a normal parameterizable function call that achieves the
    same transaction-scoped session variable.
    """
    if organization_id is not None:
        await session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": str(organization_id)},
        )
    if user_id is not None:
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )


@asynccontextmanager
async def session_scope(
    *, organization_id: str | None = None, user_id: str | None = None
) -> AsyncIterator[AsyncSession]:
    """Open a session and set the Postgres session variables Row-Level
    Security policies read from (`app.current_org_id`, `app.current_user_id`)
    before any query in this transaction runs.

    `user_id` exists because the `memberships` RLS policy allows a user to
    read their own membership row regardless of which Organization is
    currently selected (needed to discover/switch Organizations at all —
    see the rls migration and data-model.md's note on `memberships`); every
    other tenant table's policy only checks `organization_id`.

    Every tenant-scoped query MUST go through this context manager rather
    than a bare session, so RLS is never accidentally bypassed.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        await set_rls_context(session, organization_id=organization_id, user_id=user_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None

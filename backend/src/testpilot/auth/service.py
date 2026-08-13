"""Auth business logic: signup, login/logout/refresh, password reset,
profile, sessions, account deletion (FR-001-FR-010, FR-012, FR-119, DATA-004).

Deliberately framework-agnostic — the FastAPI routes in api/v1/auth.py are a
thin HTTP layer over these functions (plan.md's Library-First principle).
"""

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.audit import service as audit
from testpilot.auth.models import PasswordResetToken, RefreshToken, User
from testpilot.auth.security import (
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from testpilot.auth.tokens import create_access_token
from testpilot.core.config import get_settings
from testpilot.core.db import session_scope, set_rls_context
from testpilot.core.email import send_email
from testpilot.core.exceptions import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvalidOrExpiredTokenError,
    InvalidRefreshTokenError,
    NotFoundError,
)
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)

_FRONTEND_RESET_PASSWORD_PATH = "/reset-password"

# A real (not hand-crafted) Argon2 hash to compare against on the "unknown
# email" branch of login, so that branch takes comparable time to the
# "user exists" branch (FR-010 anti-enumeration) — computed once, lazily,
# rather than at import time, so a slow hash never delays module import.
_dummy_password_hash: str | None = None


def _get_dummy_password_hash() -> str:
    global _dummy_password_hash
    if _dummy_password_hash is None:
        _dummy_password_hash = hash_password(secrets.token_urlsafe(32))
    return _dummy_password_hash


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "org") + "-" + secrets.token_hex(3)


@dataclass(frozen=True)
class AuthResult:
    user: User
    organization: Organization
    access_token: str
    refresh_token_plain: str


@dataclass(frozen=True)
class RefreshResult:
    access_token: str
    refresh_token_plain: str


async def _get_free_plan(session: AsyncSession) -> SubscriptionPlan:
    result = await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise RuntimeError("Free subscription plan is not seeded — run migrations")
    return plan


async def _issue_refresh_token(session: AsyncSession, user_id: uuid.UUID) -> str:
    settings = get_settings()
    plain_token = generate_opaque_token()
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_opaque_token(plain_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
    )
    session.add(refresh_token)
    return plain_token


async def signup(*, email: str, password: str, name: str) -> AuthResult:
    async with session_scope() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise EmailTakenError(f"An account with email {email} already exists")

        plan = await _get_free_plan(session)

        user = User(email=email, password_hash=hash_password(password), name=name)
        session.add(user)
        await session.flush()  # assigns user.id

        # The memberships RLS policy's implicit WITH CHECK requires
        # app.current_user_id to already equal the new user's id before the
        # INSERT below is permitted — see set_rls_context's docstring.
        await set_rls_context(session, user_id=str(user.id))

        organization = Organization(
            name=f"{name}'s Organization", slug=_slugify(name), plan_id=plan.id
        )
        session.add(organization)
        await session.flush()  # assigns organization.id

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(user.id))
        session.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.owner))

        refresh_token_plain = await _issue_refresh_token(session, user.id)
        access_token = create_access_token(user_id=str(user.id), organization_id=str(organization.id))

        await session.flush()
        await session.refresh(user)
        await session.refresh(organization)

        result = AuthResult(
            user=user,
            organization=organization,
            access_token=access_token,
            refresh_token_plain=refresh_token_plain,
        )

    await audit.record(action="signup", actor_user_id=user.id, organization_id=organization.id)
    return result


async def _get_membership_and_org(session: AsyncSession, user_id: uuid.UUID) -> tuple[Membership, Organization]:
    """MVP: every user has exactly one membership (their personal Organization)."""
    result = await session.execute(select(Membership).where(Membership.user_id == user_id))
    membership = result.scalars().first()
    if membership is None:
        raise NotFoundError("No Organization membership found for this user")
    org_result = await session.execute(select(Organization).where(Organization.id == membership.organization_id))
    organization = org_result.scalar_one()
    return membership, organization


async def _organization_id_for_audit(user_id: uuid.UUID) -> uuid.UUID | None:
    """T209: every audit entry that can be tied to an Organization must
    carry one, or it can never appear in that Organization's audit log
    (FR-129) -- audit_log_entries' own RLS policy hides organization_id=NULL
    rows from every tenant-scoped read, no matter what else matches.

    Opens its own session with `user_id` set as the RLS context (rather
    than reusing the caller's session) deliberately: `memberships`' own
    policy only allows a row through when `organization_id` OR `user_id`
    matches the current session context (data-model.md), and callers here
    (logout, password reset, ...) don't have an `organization_id` to set —
    that's the whole reason this lookup exists. Never lets a lookup
    failure break the caller's actual auth operation.
    """
    try:
        async with session_scope(user_id=str(user_id)) as session:
            membership_result = await session.execute(select(Membership).where(Membership.user_id == user_id))
            membership = membership_result.scalars().first()
            return membership.organization_id if membership is not None else None
    except Exception:  # noqa: BLE001 — audit logging must never break the operation it's logging
        return None


async def login(*, email: str, password: str) -> AuthResult:
    """FR-010: an unknown email and a known-but-wrong password MUST be
    indistinguishable in response shape. Both paths run through the same
    `InvalidCredentialsError` with no branching on account existence."""
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            # Still perform a hash comparison against a dummy hash so this
            # branch takes comparable time to the "user exists" branch,
            # narrowing (not eliminating) the timing side-channel.
            verify_password(password, _get_dummy_password_hash())
            await audit.record(action="login_failed", metadata={"email": email, "reason": "unknown_account"})
            raise InvalidCredentialsError("Incorrect email or password")

        if not verify_password(password, user.password_hash):
            await audit.record(
                action="login_failed", actor_user_id=user.id, metadata={"reason": "wrong_password"}
            )
            raise InvalidCredentialsError("Incorrect email or password")

        await set_rls_context(session, user_id=str(user.id))
        _membership, organization = await _get_membership_and_org(session, user.id)
        await set_rls_context(session, organization_id=str(organization.id))

        user.last_login_at = datetime.now(UTC)
        session.add(user)

        refresh_token_plain = await _issue_refresh_token(session, user.id)
        access_token = create_access_token(user_id=str(user.id), organization_id=str(organization.id))

        await session.flush()
        await session.refresh(user)

        login_result = AuthResult(
            user=user,
            organization=organization,
            access_token=access_token,
            refresh_token_plain=refresh_token_plain,
        )

    await audit.record(action="login", actor_user_id=user.id, organization_id=organization.id)
    return login_result


async def _find_active_refresh_token(session: AsyncSession, token_plain: str) -> RefreshToken | None:
    token_hash = hash_opaque_token(token_plain)
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token = result.scalar_one_or_none()
    if token is None:
        return None
    if token.revoked_at is not None:
        return None
    if token.expires_at < datetime.now(UTC):
        return None
    return token


async def logout(*, refresh_token_plain: str) -> None:
    async with session_scope() as session:
        token = await _find_active_refresh_token(session, refresh_token_plain)
        if token is not None:
            token.revoked_at = datetime.now(UTC)
            session.add(token)
            user_id = token.user_id
            organization_id = await _organization_id_for_audit(user_id)

    if token is not None:
        await audit.record(action="logout", actor_user_id=user_id, organization_id=organization_id)


async def logout_all(*, user_id: uuid.UUID) -> None:
    async with session_scope() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        )
        now = datetime.now(UTC)
        for token in result.scalars():
            token.revoked_at = now
            session.add(token)
        organization_id = await _organization_id_for_audit(user_id)

    await audit.record(action="logout_all", actor_user_id=user_id, organization_id=organization_id)


async def refresh_session(*, refresh_token_plain: str) -> RefreshResult:
    """Rotates the refresh token on every use (research.md #3): the old
    token is revoked and a new one issued, so a stolen-but-unused old token
    becomes worthless the moment the legitimate client refreshes."""
    async with session_scope() as session:
        token = await _find_active_refresh_token(session, refresh_token_plain)
        if token is None:
            raise InvalidRefreshTokenError("Refresh token is invalid, expired, or revoked")

        token.revoked_at = datetime.now(UTC)
        token.last_used_at = datetime.now(UTC)
        session.add(token)

        await set_rls_context(session, user_id=str(token.user_id))
        _membership, organization = await _get_membership_and_org(session, token.user_id)

        new_refresh_token_plain = await _issue_refresh_token(session, token.user_id)
        access_token = create_access_token(user_id=str(token.user_id), organization_id=str(organization.id))

        return RefreshResult(access_token=access_token, refresh_token_plain=new_refresh_token_plain)


async def forgot_password(*, email: str) -> None:
    """FR-010: always returns successfully regardless of whether the email
    exists — the caller (route) always responds 202; this function simply
    no-ops for an unknown email instead of raising."""
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return

        plain_token = generate_opaque_token()
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_opaque_token(plain_token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

        reset_link = f"{_FRONTEND_RESET_PASSWORD_PATH}?token={plain_token}"
        send_email(
            to=user.email,
            subject="Reset your TestPilot AI password",
            body=(
                f"We received a request to reset your TestPilot AI password. "
                f"Use the link below within the next hour:\n\n{reset_link}\n\n"
                f"If you didn't request this, you can safely ignore this email."
            ),
        )
        user_id = user.id
        organization_id = await _organization_id_for_audit(user_id)

    await audit.record(action="password_reset_requested", actor_user_id=user_id, organization_id=organization_id)


async def reset_password(*, token_plain: str, new_password: str) -> None:
    async with session_scope() as session:
        token_hash = hash_opaque_token(token_plain)
        result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()

        if (
            token is None
            or token.used_at is not None
            or token.expires_at < datetime.now(UTC)
        ):
            raise InvalidOrExpiredTokenError("Password reset token is invalid, expired, or already used")

        user_result = await session.execute(select(User).where(User.id == token.user_id))
        user = user_result.scalar_one()
        user.password_hash = hash_password(new_password)
        session.add(user)

        token.used_at = datetime.now(UTC)
        session.add(token)

        # Invalidate every existing session — a password reset is a strong
        # signal the previous credential may have been compromised.
        await logout_all(user_id=user.id)
        user_id = user.id
        organization_id = await _organization_id_for_audit(user_id)

    await audit.record(action="password_reset_completed", actor_user_id=user_id, organization_id=organization_id)


async def change_password(*, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
    async with session_scope(user_id=str(user_id)) as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()

        if not verify_password(current_password, user.password_hash):
            raise InvalidCurrentPasswordError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        session.add(user)
        organization_id = await _organization_id_for_audit(user_id)

    await audit.record(action="password_changed", actor_user_id=user_id, organization_id=organization_id)


async def get_me(*, user_id: uuid.UUID) -> tuple[User, Organization, MembershipRole]:
    async with session_scope(user_id=str(user_id)) as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        membership, organization = await _get_membership_and_org(session, user_id)
        return user, organization, membership.role


async def update_profile(*, user_id: uuid.UUID, name: str | None, email: str | None) -> User:
    async with session_scope(user_id=str(user_id)) as session:
        if email is not None:
            existing = await session.execute(select(User).where(User.email == email, User.id != user_id))
            if existing.scalar_one_or_none() is not None:
                raise EmailTakenError(f"An account with email {email} already exists")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user


async def list_sessions(*, user_id: uuid.UUID, current_refresh_token_plain: str | None) -> list[tuple[RefreshToken, bool]]:
    current_hash = hash_opaque_token(current_refresh_token_plain) if current_refresh_token_plain else None
    async with session_scope() as session:
        result = await session.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .order_by(RefreshToken.created_at.desc())
        )
        tokens = result.scalars().all()
        return [(t, t.token_hash == current_hash) for t in tokens]


async def revoke_session(*, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    async with session_scope() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.id == session_id, RefreshToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()
        if token is None:
            raise NotFoundError("Session not found")
        token.revoked_at = datetime.now(UTC)
        session.add(token)


async def delete_account(*, user_id: uuid.UUID) -> None:
    """DATA-004: anonymizes the user row (tombstone email, is_active=false)
    rather than hard-deleting, preserving referential integrity of
    Organization-owned records they created."""
    async with session_scope(user_id=str(user_id)) as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.email = f"deleted-user-{user.id}@testpilot.invalid"
        user.name = "Deleted User"
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.is_active = False
        session.add(user)
        await logout_all(user_id=user_id)
        organization_id = await _organization_id_for_audit(user_id)

    await audit.record(action="account_deleted", actor_user_id=user_id, organization_id=organization_id)

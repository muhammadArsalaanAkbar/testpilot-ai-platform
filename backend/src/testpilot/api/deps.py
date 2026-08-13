"""Shared FastAPI dependencies: authenticated-user/organization resolution
and rate limiting (research.md #4, #12; FR-133, SEC-003, SEC-009)."""

from dataclasses import dataclass

from fastapi import Header
from slowapi import Limiter
from slowapi.util import get_remote_address

from testpilot.auth.tokens import decode_access_token
from testpilot.core.config import get_settings
from testpilot.core.exceptions import NotAuthenticatedError
from testpilot.core.logging import bind_context

# Redis-backed (not in-memory) so limits are correct across multiple API
# process instances (research.md #12, NFR-005). Keyed by remote IP; per-
# account (email) throttling is a natural additional layer — reading the
# validated request body inside a rate-limit key function is fragile with
# slowapi's sync key-function model, so it is intentionally deferred rather
# than half-implemented under this task's scope.
#
# Disabled in the test environment: the automated suite fires many requests
# from the same simulated client address in quick succession by design (e.g.
# repeated signups across independent test cases), which is not the
# behavior SEC-009 rate limiting is meant to catch — dedicated rate-limit
# *behavior* testing belongs to Phase 20's security hardening pass (T199),
# not to every unrelated auth test incidentally tripping the limiter.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_settings().redis_url,
    enabled=get_settings().environment != "test",
)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    organization_id: str


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Resolves the authenticated user and the Organization their session is
    scoped to from the JWT access token's claims (SEC-003: every endpoint
    enforces both authentication and authorization independently).

    The access token MUST be sent via the `Authorization` header, never
    relied upon from a cookie — this is deliberate (plan.md Security
    Architecture): a browser attaches cookies automatically to cross-site
    requests, but never an `Authorization` header, so requiring it here is
    itself a CSRF defense, on top of the refresh cookie's `SameSite=Lax`.

    `async def`, despite doing no I/O, is deliberate: FastAPI runs a *sync*
    `Depends()` callable in a threadpool, and `contextvars.ContextVar.set()`
    inside a threadpool thread does not propagate back to the request's own
    async context (verified empirically — a real, easy-to-miss FastAPI
    gotcha) — so `bind_context(...)` below would silently never be visible
    to any log statement the route handler or service layer makes. Running
    inline on the event loop, as every async dependency does, avoids that.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise NotAuthenticatedError("Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ")
    payload = decode_access_token(token)
    # NFR-009: every log statement from here on in this request carries the
    # authenticated identity, the same way the correlation-ID middleware
    # already does for the request as a whole.
    bind_context(organization_id=payload.organization_id, user_id=payload.user_id)
    return CurrentUser(user_id=payload.user_id, organization_id=payload.organization_id)

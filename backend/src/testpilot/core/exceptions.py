"""Shared domain exceptions and the FastAPI handler that maps them to the
`{"error": {"code", "message", "details"}}` envelope documented in
contracts/_conventions.md.

Libraries raise these typed exceptions instead of returning sentinel values
or raw HTTPExceptions, so the mapping from domain error to HTTP response
lives in exactly one place (register_exception_handlers below).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class TestPilotError(Exception):
    """Base class for all domain-raised errors."""

    code: str = "internal_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(TestPilotError):
    """Raised for both "does not exist" and "exists in another Organization".

    These two cases are deliberately indistinguishable at this layer (FR-136,
    SEC-011) — callers must never have a separate "forbidden" exception for
    cross-tenant access.
    """

    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ValidationFailedError(TestPilotError):
    code = "validation_failed"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class InvalidUrlError(TestPilotError):
    """Malformed URL (not a well-formed http(s) URL) — contracts/projects-api.md."""

    code = "invalid_url"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class UrlNotPublicError(TestPilotError):
    """URL resolves to a private/loopback/link-local/reserved network range
    (SEC-006/FR-035/FR-135 SSRF guard) — contracts/projects-api.md."""

    code = "url_not_public"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class ConfirmationRequiredError(TestPilotError):
    """A destructive action (project hard-delete, FR-029) was requested
    without the required explicit `{confirm: true}` body."""

    code = "confirmation_required"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class ProjectArchivedError(TestPilotError):
    """A test run or AI generation request was made against an archived
    project (FR-032) — contracts/projects-api.md."""

    code = "project_archived"
    status_code = status.HTTP_409_CONFLICT


class ConflictError(TestPilotError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class EmailTakenError(ConflictError):
    code = "email_taken"


class InvalidOrExpiredTokenError(TestPilotError):
    code = "invalid_or_expired_token"
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidCurrentPasswordError(TestPilotError):
    code = "invalid_current_password"
    status_code = status.HTTP_401_UNAUTHORIZED


class PlanLimitExceededError(TestPilotError):
    code = "plan_limit_exceeded"
    status_code = status.HTTP_402_PAYMENT_REQUIRED

    def __init__(self, message: str, *, limit: str, used: int, max_allowed: int) -> None:
        super().__init__(message, details={"limit": limit, "used": used, "max": max_allowed})


class InvalidCredentialsError(TestPilotError):
    code = "invalid_credentials"
    status_code = status.HTTP_401_UNAUTHORIZED


class NotAuthenticatedError(TestPilotError):
    code = "not_authenticated"
    status_code = status.HTTP_401_UNAUTHORIZED


class InvalidRefreshTokenError(TestPilotError):
    code = "invalid_or_expired_refresh_token"
    status_code = status.HTTP_401_UNAUTHORIZED


class InsufficientRoleError(TestPilotError):
    """For a same-tenant action the caller's role doesn't permit (e.g. a
    non-owner/admin member attempting an owner/admin-only write). Distinct
    from NotFoundError: this is a real, disclosable 403 — the resource is
    visibly the caller's own Organization, so there is nothing to mask,
    unlike cross-tenant access (FR-136/SEC-011), which must return 404."""

    code = "insufficient_role"
    status_code = status.HTTP_403_FORBIDDEN


class RateLimitedError(TestPilotError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class NotImplementedYetError(TestPilotError):
    """For documented Future-scope endpoint stubs (e.g. invitations, member removal)."""

    code = "not_implemented"
    status_code = status.HTTP_501_NOT_IMPLEMENTED


def _error_response(exc: TestPilotError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TestPilotError)
    async def _handle_testpilot_error(request: Request, exc: TestPilotError) -> JSONResponse:
        return _error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Request-body/query/path validation (FastAPI/Pydantic) uses a
        # different exception type than our own ValidationFailedError, but
        # MUST produce the same envelope shape/code (contracts/_conventions.md)
        # so the frontend has one error-handling code path either way.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_failed",
                    "message": "Request validation failed",
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )

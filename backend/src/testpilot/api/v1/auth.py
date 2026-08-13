"""Auth routes (contracts/auth-api.md). Thin HTTP layer over auth/service.py."""

import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from testpilot.api.deps import CurrentUser, get_current_user, limiter
from testpilot.auth import service
from testpilot.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrganizationPublic,
    RefreshResponse,
    ResetPasswordRequest,
    SessionPublic,
    SessionsListResponse,
    SignupRequest,
    SignupResponse,
    UpdateProfileRequest,
    UserPublic,
)
from testpilot.core.config import get_settings
from testpilot.core.exceptions import InvalidRefreshTokenError

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        # Secure cookies are only ever resent over HTTPS. "local" (no TLS by
        # default) and "test" (the ASGI test transport has no TLS concept at
        # all — httpx correctly refuses to resend a Secure cookie over its
        # http:// base_url) both need this off; every real deployment
        # (staging/production) gets Secure=True.
        secure=settings.environment not in ("local", "test"),
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path=_REFRESH_COOKIE_PATH)


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
@limiter.limit("5/minute")
async def signup(request: Request, payload: SignupRequest, response: Response) -> SignupResponse:
    result = await service.signup(email=payload.email, password=payload.password, name=payload.name)
    _set_refresh_cookie(response, result.refresh_token_plain)
    return SignupResponse(
        user=UserPublic.model_validate(result.user, from_attributes=True),
        organization=OrganizationPublic.model_validate(result.organization, from_attributes=True),
        access_token=result.access_token,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, response: Response) -> LoginResponse:
    result = await service.login(email=payload.email, password=payload.password)
    _set_refresh_cookie(response, result.refresh_token_plain)
    return LoginResponse(
        user=UserPublic.model_validate(result.user, from_attributes=True),
        access_token=result.access_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME)
) -> None:
    if refresh_token is not None:
        await service.logout(refresh_token_plain=refresh_token)
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(response: Response, current_user: CurrentUser = Depends(get_current_user)) -> None:
    await service.logout_all(user_id=uuid.UUID(current_user.user_id))
    _clear_refresh_cookie(response)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response, refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME)
) -> RefreshResponse:
    if refresh_token is None:
        raise InvalidRefreshTokenError("No refresh token cookie present")
    result = await service.refresh_session(refresh_token_plain=refresh_token)
    _set_refresh_cookie(response, result.refresh_token_plain)
    return RefreshResponse(access_token=result.access_token)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def forgot_password(request: Request, payload: ForgotPasswordRequest) -> None:
    await service.forgot_password(email=payload.email)


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest) -> dict[str, bool]:
    await service.reset_password(token_plain=payload.token, new_password=payload.new_password)
    return {"success": True}


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    user, organization, role = await service.get_me(user_id=uuid.UUID(current_user.user_id))
    return MeResponse(
        user=UserPublic.model_validate(user, from_attributes=True),
        organization=OrganizationPublic.model_validate(organization, from_attributes=True),
        role=role.value,
    )


@router.patch("/me", response_model=dict)
async def update_me(
    payload: UpdateProfileRequest, current_user: CurrentUser = Depends(get_current_user)
) -> dict[str, UserPublic]:
    user = await service.update_profile(
        user_id=uuid.UUID(current_user.user_id), name=payload.name, email=payload.email
    )
    return {"user": UserPublic.model_validate(user, from_attributes=True)}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(response: Response, current_user: CurrentUser = Depends(get_current_user)) -> None:
    await service.delete_account(user_id=uuid.UUID(current_user.user_id))
    _clear_refresh_cookie(response)


@router.post("/me/change-password")
async def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUser = Depends(get_current_user)
) -> dict[str, bool]:
    await service.change_password(
        user_id=uuid.UUID(current_user.user_id),
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return {"success": True}


@router.get("/me/sessions", response_model=SessionsListResponse)
async def list_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> SessionsListResponse:
    sessions = await service.list_sessions(
        user_id=uuid.UUID(current_user.user_id), current_refresh_token_plain=refresh_token
    )
    return SessionsListResponse(
        items=[
            SessionPublic(
                id=token.id, created_at=token.created_at, last_used_at=token.last_used_at, is_current=is_current
            )
            for token, is_current in sessions
        ]
    )


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> None:
    await service.revoke_session(user_id=uuid.UUID(current_user.user_id), session_id=session_id)

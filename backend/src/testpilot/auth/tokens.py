"""JWT access-token sign/verify utilities (SEC-002: secure, expiring
sessions). Short-lived (Settings.jwt_access_token_ttl_minutes) by design —
the refresh token (auth/models.py's RefreshToken, server-side revocable) is
what actually survives logout; the access token is left to simply expire."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from testpilot.core.config import get_settings
from testpilot.core.exceptions import NotAuthenticatedError

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: str
    organization_id: str


def create_access_token(*, user_id: str, organization_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "org_id": organization_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> AccessTokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_signing_key, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise NotAuthenticatedError("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise NotAuthenticatedError("Invalid access token") from exc

    user_id = payload.get("sub")
    organization_id = payload.get("org_id")
    if not isinstance(user_id, str) or not isinstance(organization_id, str):
        raise NotAuthenticatedError("Malformed access token")

    return AccessTokenPayload(user_id=user_id, organization_id=organization_id)

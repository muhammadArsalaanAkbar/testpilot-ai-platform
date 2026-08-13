"""Password hashing utilities (SEC-001: modern, salted, adaptive hashing;
plaintext or reversibly-encrypted passwords MUST NOT be stored)."""

import hashlib
import secrets

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    # passlib ships no type stubs, so CryptContext methods return Any.
    return str(_pwd_context.hash(plain_password))


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bool(_pwd_context.verify(plain_password, password_hash))


def generate_opaque_token() -> str:
    """A high-entropy random token for refresh/password-reset tokens (not a
    user-chosen secret, so a fast deterministic hash — not Argon2 — is the
    correct/standard choice for the paired `hash_opaque_token` below: these
    tokens must be looked up by exact hash equality, which Argon2's
    per-call salting makes impossible)."""
    return secrets.token_urlsafe(32)


def hash_opaque_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode("utf-8")).hexdigest()

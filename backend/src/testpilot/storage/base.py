"""ArtifactStorage Protocol — the provider-agnostic object-storage boundary
(DATA-002, INT-004, T149).

Mirrors `ai_provider/base.py`'s `LLMProvider` pattern: callers (`execution`,
`api/v1/testruns.py`) depend only on this interface, never on `boto3` or any
storage-vendor-specific type, so the backend stays swappable (plan.md
Screenshot & Artifact Storage Architecture: "Only this module talks to
boto3."). The concrete adapter is `storage/s3.py`, which speaks the same
S3-compatible API against either AWS S3 (production) or MinIO (local/CI).
"""

from __future__ import annotations

from typing import Protocol


class ArtifactNotFoundError(Exception):
    """Raised by `get_url` when `storage_key` does not exist in the backend
    — e.g. it was already purged (DATA-003) or never successfully uploaded."""


class ArtifactStorage(Protocol):
    async def put(self, data: bytes, content_type: str) -> str:
        """Uploads `data` and returns its `storage_key` — an opaque
        identifier the caller persists (never a public URL; see `get_url`)."""
        ...

    async def get_url(self, storage_key: str, expires_in: int) -> str:
        """Returns a short-lived signed URL for `storage_key`, valid for
        `expires_in` seconds (SEC-013: the frontend never receives a raw
        storage credential or bucket path). Raises `ArtifactNotFoundError`
        if `storage_key` does not exist."""
        ...

    async def delete(self, storage_key: str) -> None:
        """Permanently deletes the object at `storage_key` (DATA-003's
        retention purge — the physical binary, not just the DB reference).
        Deleting an already-absent key is a no-op, not an error (mirrors
        S3's own idempotent DeleteObject semantics)."""
        ...

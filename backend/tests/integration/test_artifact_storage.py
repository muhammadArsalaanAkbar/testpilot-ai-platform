"""Integration test: artifact upload/retrieval round-trip via a real local
MinIO instance (T147, DATA-002, plan.md Screenshot & Artifact Storage
Architecture). Exercises the real `S3ArtifactStorage` adapter — no fake/mock
storage — against the S3-compatible MinIO server this dev environment runs
locally (docker container `testpilot-minio`), never real AWS credentials.
"""

import uuid

import httpx
import pytest

from testpilot.core.config import get_settings
from testpilot.storage.s3 import S3ArtifactStorage

pytestmark = pytest.mark.anyio


def _storage() -> S3ArtifactStorage:
    settings = get_settings()
    return S3ArtifactStorage(
        endpoint_url=settings.object_storage_endpoint_url,
        bucket=settings.object_storage_bucket,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        region=settings.object_storage_region,
    )


async def test_put_then_get_url_round_trips_the_original_bytes():
    storage = _storage()
    payload = f"fixture-{uuid.uuid4()}".encode() * 100

    storage_key = await storage.put(payload, content_type="image/png")
    assert storage_key

    url = await storage.get_url(storage_key, expires_in=60)
    assert url.startswith("http")

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"] == "image/png"


async def test_two_puts_of_the_same_bytes_get_distinct_keys():
    """Storage keys must not collide even for identical content — each
    capture is its own artifact, not content-addressed/deduplicated."""
    storage = _storage()
    payload = b"identical bytes"

    key_a = await storage.put(payload, content_type="image/png")
    key_b = await storage.put(payload, content_type="image/png")

    assert key_a != key_b


async def test_signed_url_respects_content_disposition_not_inline_executable():
    """SEC-013: artifacts must never be served in a way a browser would
    execute as active content — enforced via an explicit attachment-style
    Content-Disposition on the object, not relied upon from content-type
    alone."""
    storage = _storage()
    storage_key = await storage.put(b"<script>alert(1)</script>", content_type="text/plain")

    url = await storage.get_url(storage_key, expires_in=60)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "").lower()


async def test_get_url_for_a_missing_key_raises_a_typed_not_found_error():
    from testpilot.storage.base import ArtifactNotFoundError

    storage = _storage()
    with pytest.raises(ArtifactNotFoundError):
        await storage.get_url(f"nonexistent/{uuid.uuid4()}.png", expires_in=60)


async def test_signed_url_expires_after_the_requested_window():
    """A signed URL is only valid for the requested duration — a URL minted
    with a 1-second expiry must be rejected by the storage backend shortly
    after, not remain valid indefinitely."""
    import asyncio

    storage = _storage()
    storage_key = await storage.put(b"expiring content", content_type="image/png")

    url = await storage.get_url(storage_key, expires_in=1)
    await asyncio.sleep(2)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    assert response.status_code in (400, 403)

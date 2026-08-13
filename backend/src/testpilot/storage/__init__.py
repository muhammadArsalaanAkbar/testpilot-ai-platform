"""Artifact storage selection (research.md #8): settings-driven construction
of the concrete `ArtifactStorage` adapter, mirroring `ai_provider`'s
`get_provider()` — callers depend only on the `ArtifactStorage` Protocol."""

from functools import lru_cache

from testpilot.core.config import get_settings
from testpilot.storage.base import ArtifactStorage


@lru_cache
def get_storage() -> ArtifactStorage:
    settings = get_settings()
    from testpilot.storage.s3 import S3ArtifactStorage

    return S3ArtifactStorage(
        bucket=settings.object_storage_bucket,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        region=settings.object_storage_region,
        endpoint_url=settings.object_storage_endpoint_url,
    )

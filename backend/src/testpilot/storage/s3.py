"""S3/MinIO `ArtifactStorage` adapter (T150, research.md #8, SEC-013).

The same S3-compatible `boto3` client works against AWS S3 (production,
`endpoint_url=None`) and MinIO (local dev/CI, `endpoint_url=http://...`) —
only the constructor arguments differ, never the code path (research.md #8's
whole rationale for standardizing on the S3 API). `boto3` is synchronous;
every call here runs on a thread via `asyncio.to_thread` so it never blocks
the event loop of the async API/worker process calling it.

Bucket provisioning (creation, lifecycle policy) is deliberately NOT this
adapter's job — it only ever calls PutObject/HeadObject/GetObject, the
minimum a least-privilege application IAM role needs (SEC-013's spirit
applied to the storage credential itself, not just the served content).
"""

from __future__ import annotations

import asyncio
import uuid

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from testpilot.storage.base import ArtifactNotFoundError


class S3ArtifactStorage:
    """Concrete `ArtifactStorage` (storage/base.py's Protocol)."""

    def __init__(
        self,
        *,
        bucket: str,
        access_key: str | None,
        secret_key: str | None,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            # MinIO's virtual-hosted-style addressing needs a real DNS entry
            # per bucket, which a bare `localhost` endpoint doesn't have —
            # path-style ("http://host/bucket/key") works against both MinIO
            # and S3, so it is used unconditionally rather than branching on
            # which backend this is.
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def put(self, data: bytes, content_type: str) -> str:
        storage_key = f"artifacts/{uuid.uuid4()}"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=storage_key,
            Body=data,
            ContentType=content_type,
            # SEC-013: never served as inline/executable content, regardless
            # of content_type — a browser is told to download, not render.
            ContentDisposition="attachment",
        )
        return storage_key

    async def get_url(self, storage_key: str, expires_in: int) -> str:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=storage_key)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404 or exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                raise ArtifactNotFoundError(f"No artifact at {storage_key!r}") from exc
            raise

        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=storage_key)

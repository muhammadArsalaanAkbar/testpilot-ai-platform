#!/bin/sh
# T224: creates the local artifact bucket (research.md #8) if it doesn't
# already exist. Bucket provisioning is deliberately not the application's
# own job (storage/s3.py's module docstring — it only ever calls
# PutObject/HeadObject/GetObject/DeleteObject) — this script is that
# provisioning step, run once against the `minio` service via the
# `minio/mc` (MinIO Client) image in docker-compose.yml, never against
# production S3.
set -e

mc alias set local "$OBJECT_STORAGE_ENDPOINT_URL" "$OBJECT_STORAGE_ACCESS_KEY" "$OBJECT_STORAGE_SECRET_KEY"

if mc ls "local/$OBJECT_STORAGE_BUCKET" >/dev/null 2>&1; then
  echo "bucket '$OBJECT_STORAGE_BUCKET' already exists"
else
  mc mb "local/$OBJECT_STORAGE_BUCKET"
  echo "created bucket '$OBJECT_STORAGE_BUCKET'"
fi

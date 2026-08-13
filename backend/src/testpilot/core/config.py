from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration, loaded from environment variables.

    Validated eagerly at import/startup time so a missing or malformed value
    fails fast instead of surfacing later as an obscure runtime error.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"

    database_url: str = Field(
        ...,
        description=(
            "Async SQLAlchemy URL for the API/worker/CLI runtime connection. MUST authenticate "
            "as a non-superuser, non-table-owner role for Postgres Row-Level Security to have "
            "any effect (RLS never applies to superusers or, without FORCE, to table owners — "
            "see the rls_role_and_policies migration). Example: "
            "postgresql+asyncpg://testpilot_app:...@host/db"
        ),
    )
    migrations_database_url: str | None = Field(
        default=None,
        description=(
            "Async SQLAlchemy URL used only by Alembic for schema migrations (needs DDL/role-"
            "management privileges the least-privilege runtime role in database_url must not "
            "have). Falls back to database_url if unset — but that only works for a role with "
            "sufficient privileges, which the runtime role deliberately is not once RLS role "
            "separation is configured."
        ),
    )
    redis_url: str = Field(..., description="Redis URL used for the job queue, rate limits, and cache")

    jwt_signing_key: str = Field(..., min_length=32)
    jwt_access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    ai_provider: Literal["fake", "cloud"] = "fake"
    ai_provider_api_key: str | None = None
    ai_provider_model: str = "claude-sonnet-5"

    object_storage_endpoint_url: str | None = None
    object_storage_bucket: str = "testpilot-artifacts"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_region: str = "us-east-1"

    sentry_dsn: str | None = None

    # SMTP relay for transactional email (INT-003). None = log-only (CI /
    # minimal setups without a mail catcher configured). Local dev points
    # this at Mailhog (quickstart.md: "check your local mail catcher").
    smtp_host: str | None = None
    smtp_port: int = 1025
    email_from_address: str = "no-reply@testpilot.invalid"

    cors_allowed_origins: list[str] = ["http://localhost:3200"]

    artifact_retention_days: int = 90

    # NFR-011: the worker process has no FastAPI app of its own for
    # `prometheus-fastapi-instrumentator` to expose `/metrics` on (unlike
    # the API process) — worker/main.py starts a bare
    # `prometheus_client.start_http_server` on this port instead, so
    # job-duration/error-rate counters recorded in-process (worker/jobs/*.py)
    # are scrapeable independently of the API's own metrics endpoint.
    worker_metrics_port: int = 9200


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Shared pytest fixtures.

Loads .env.test *before* any `testpilot` module is imported, so
`get_settings()` (module-level `@lru_cache`) builds its one cached Settings
instance from the test configuration rather than whatever `.env` a
developer's shell happens to have loaded.

Uses a real Postgres database (never SQLite) per research.md #14 — RLS
policies and Postgres-specific behavior can only be verified against real
Postgres. A minimal version of this fixture set is established here in
Phase 4 (User Story 1) ahead of the dedicated Phase 21 (Automated Testing
Infrastructure) hardening pass; Phase 21 extends this file, it does not
replace it.
"""

from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.test", override=True)

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from testpilot.api.main import create_app
from testpilot.core.config import get_settings
from testpilot.core.db import dispose_engine
from testpilot.core.redis import dispose_redis

# Registers `fixture_site_url` (tests/fixtures/server.py, T133) as a pytest
# plugin so any test module can use it as a fixture parameter without a
# direct `from tests.fixtures.server import fixture_site_url` import — that
# import pattern makes every test function parameter of the same name look
# like an unused-import redefinition to ruff (F811).
pytest_plugins = ["tests.fixtures.server"]


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test() -> AsyncIterator[None]:
    """core/db.py and core/redis.py each cache an async client as a
    module-level singleton (by design — the app creates one for its whole
    process lifetime). But pytest-asyncio gives each test function its own
    event loop, and both asyncpg and redis-py connections are bound to the
    loop they were created on; reusing a cached client across tests'
    different event loops corrupts connection teardown (manifests as
    `RuntimeError: Event loop is closed`, seemingly at random — for
    asyncpg specifically, sometimes instead as `AttributeError: 'NoneType'
    object has no attribute 'send'`). Disposing both cached clients before
    and after every test forces fresh ones bound to that test's own loop.
    """
    await dispose_engine()
    await dispose_redis()
    yield
    await dispose_engine()
    await dispose_redis()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    """Truncates every per-test-mutable table before each test.

    Uses the migrations/admin connection, not the app's own least-privilege
    role, because TRUNCATE was deliberately not granted to that role (tests
    are exercising application behavior, not whether the app role can
    truncate tables). `subscription_plans` is intentionally excluded — it is
    seeded reference data every test relies on existing.
    """
    settings = get_settings()
    admin_url = settings.migrations_database_url or settings.database_url
    engine = create_async_engine(admin_url)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE memberships, refresh_tokens, password_reset_tokens, audit_log_entries, "
            "users, organizations RESTART IDENTITY CASCADE"
        )
    await engine.dispose()
    yield


@pytest.fixture(autouse=True)
def _clean_queues() -> None:
    """Flushes the test Redis DB's RQ queues before each test.

    Contract/integration tests that hit generate/regenerate endpoints push
    real jobs onto the real (test-DB-indexed) Redis queue — nothing else
    clears them, since no worker consumes the test queue during a normal
    pytest run. Without this, queue length would grow unbounded across a
    long test session; flushing keeps each test's queue state hermetic.
    """
    from testpilot.worker.queues import get_sync_redis

    get_sync_redis().flushdb()


@pytest.fixture(autouse=True, scope="session")
def _require_test_environment() -> None:
    """Guards against ever running the (destructive, truncating) test suite
    against a non-test database by accident."""
    if get_settings().environment != "test":
        raise RuntimeError(
            "Tests must run with ENVIRONMENT=test (see .env.test) — refusing to run "
            f"against environment={get_settings().environment!r} to avoid truncating real data."
        )
    if "_test" not in get_settings().database_url:
        raise RuntimeError(
            "DATABASE_URL does not look like a test database (expected '_test' in the name) — "
            "refusing to run the test suite, which truncates tables on every test."
        )

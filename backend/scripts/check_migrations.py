"""CI check (T204, constitution's Technology & Quality Constraints): confirms
every Alembic migration applies cleanly, in order, to a genuinely fresh
(zero pre-existing tables) database, and that the resulting schema has no
drift from the current SQLModel metadata. Catches two distinct failure
modes `alembic check` against the long-lived dev/test databases can't: a
migration that only "works" because the target database already happened
to have some prerequisite state, and a broken migration *chain* (a bad
`down_revision` link, a syntax error in an old migration nobody re-runs
locally) — as opposed to `alembic check`'s job of catching an ORM model
change that was never captured in any migration at all.

Reuses the `alembic` CLI as a subprocess against a disposable database,
rather than reimplementing `command.upgrade`/`command.check` via alembic's
Python API, so this exercises the exact same code path a developer running
`alembic upgrade head` by hand does.

Usage: python scripts/check_migrations.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _with_database(url: str, database: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _asyncpg_dsn(url: str) -> str:
    """asyncpg.connect() doesn't understand the `+asyncpg` SQLAlchemy driver
    suffix or `postgresql+asyncpg://` as a scheme — strip it."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _create_database(admin_url: str, database: str) -> None:
    conn = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await conn.execute(f'CREATE DATABASE "{database}"')
    finally:
        await conn.close()


async def _drop_database(admin_url: str, database: str) -> None:
    conn = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        # A DROP DATABASE fails while any session still holds a connection
        # to it -- terminate stragglers first (this script's own alembic
        # subprocesses should have already disconnected, but a hung
        # connection here must not leak the disposable database forever).
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            database,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}"')
    finally:
        await conn.close()


def _run_alembic(args: list[str], *, database_url: str, migrations_database_url: str) -> subprocess.CompletedProcess[str]:
    import os

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["MIGRATIONS_DATABASE_URL"] = migrations_database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    from testpilot.core.config import get_settings

    settings = get_settings()
    admin_url = settings.migrations_database_url or settings.database_url
    temp_db_name = f"testpilot_migration_check_{uuid.uuid4().hex[:12]}"
    temp_url = _with_database(admin_url, temp_db_name)

    print(f"Creating disposable database {temp_db_name}...")
    asyncio.run(_create_database(admin_url, temp_db_name))

    try:
        print("Applying every migration to it from scratch...")
        upgrade_result = _run_alembic(["upgrade", "head"], database_url=temp_url, migrations_database_url=temp_url)
        print(upgrade_result.stdout)
        if upgrade_result.returncode != 0:
            print(upgrade_result.stderr, file=sys.stderr)
            print("FAILED: the migration chain does not apply cleanly to a fresh database.")
            return 1

        print("Checking for schema drift against current models...")
        check_result = _run_alembic(["check"], database_url=temp_url, migrations_database_url=temp_url)
        print(check_result.stdout)
        if check_result.returncode != 0:
            print(check_result.stderr, file=sys.stderr)
            print("FAILED: the migrated schema drifts from the current SQLModel metadata.")
            return 1

        print("OK: migrations apply cleanly to a fresh database with zero drift.")
        return 0
    finally:
        print(f"Dropping disposable database {temp_db_name}...")
        asyncio.run(_drop_database(admin_url, temp_db_name))


if __name__ == "__main__":
    raise SystemExit(main())

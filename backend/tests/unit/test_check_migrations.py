"""Unit tests for scripts/check_migrations.py's pure URL-manipulation
helpers (T204). The script's actual value — creating a real disposable
database, applying every migration to it from scratch, and diffing the
result against current models — is inherently an integration-level
behavior verified by running the script itself (see the Phase 19
checkpoint report), not something worth faking with a mocked Postgres."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_migrations import _asyncpg_dsn, _with_database  # noqa: E402


def test_with_database_replaces_only_the_database_name():
    url = "postgresql+asyncpg://testpilot:testpilot@localhost:5435/testpilot"
    assert _with_database(url, "some_temp_db") == "postgresql+asyncpg://testpilot:testpilot@localhost:5435/some_temp_db"


def test_asyncpg_dsn_strips_the_sqlalchemy_driver_suffix():
    url = "postgresql+asyncpg://testpilot:testpilot@localhost:5435/testpilot"
    assert _asyncpg_dsn(url) == "postgresql://testpilot:testpilot@localhost:5435/testpilot"

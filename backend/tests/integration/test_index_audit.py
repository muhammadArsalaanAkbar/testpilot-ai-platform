"""T203: full index audit — every index documented in data-model.md must
exist on the real schema, across every table. Queries pg_indexes directly
(not SQLAlchemy metadata) so this catches drift between the ORM model
declarations and what actually got migrated, not just what the models
currently claim.
"""

import re

import pytest
from sqlalchemy import text

from testpilot.core.db import get_engine

# {table: [(columns-in-order, is_unique), ...]} exactly as documented in
# data-model.md's per-table "Indexes" lines. Primary keys are omitted (a
# PK's implicit unique index is a given, not something data-model.md calls
# out separately). GIN indexes are included by column name only -- the
# access method is verified in a dedicated GIN-specific test below.
_DOCUMENTED_INDEXES: dict[str, list[tuple[tuple[str, ...], bool]]] = {
    "users": [(("email",), True)],
    "organizations": [(("slug",), True)],
    "memberships": [(("organization_id", "user_id"), True), (("user_id",), False)],
    "refresh_tokens": [(("token_hash",), True), (("user_id", "revoked_at"), False)],
    "projects": [(("organization_id", "status"), False)],
    "test_cases": [(("project_id", "status"), False), (("organization_id",), False)],
    "test_steps": [(("test_case_id", "order_index"), True), (("test_case_id",), False)],
    "test_runs": [(("project_id", "created_at"), False), (("organization_id", "status"), False)],
    "test_run_cases": [(("test_run_id", "test_case_id"), True), (("test_run_id",), False)],
    "test_results": [
        (("test_run_id",), False),
        (("test_case_id", "started_at"), False),
        (("organization_id", "status"), False),
    ],
    "artifacts": [(("test_result_id",), False)],
    "ai_analyses": [(("test_result_id", "created_at"), False)],
    "generation_runs": [(("project_id", "status"), False)],
    "issues": [(("project_id", "status"), False), (("organization_id", "severity"), False)],
    "issue_attachments": [(("issue_id",), False)],
    "notifications": [(("user_id", "read_at"), False), (("user_id", "created_at"), False)],
    "subscription_plans": [(("tier",), True)],
    "usage_records": [
        (("organization_id", "period_start", "metric"), True),
        (("organization_id", "metric"), False),
    ],
    "audit_log_entries": [(("organization_id", "created_at"), False), (("actor_user_id", "created_at"), False)],
}

_GIN_INDEXES = {
    "test_cases": ["tags", "search_vector"],
}

_INDEXDEF_COLUMNS_RE = re.compile(r"\(([^)]+)\)\s*$")


def _parse_columns(indexdef: str) -> tuple[str, ...]:
    match = _INDEXDEF_COLUMNS_RE.search(indexdef)
    assert match, f"could not parse columns from indexdef: {indexdef}"
    # Strip a trailing " DESC"/" ASC" per column -- column identity, not
    # sort direction, is what's being audited here (see module docstring
    # in tests/integration/test_index_audit.py's companion note below).
    return tuple(part.strip().split(" ")[0] for part in match.group(1).split(","))


async def _load_indexes(conn) -> dict[str, list[tuple[tuple[str, ...], bool, str]]]:
    result = await conn.execute(
        text(
            "SELECT tablename, indexname, indexdef, indexdef ILIKE '%UNIQUE%' AS is_unique, "
            "CASE WHEN indexdef ILIKE '%USING gin%' THEN 'gin' ELSE 'btree' END AS method "
            "FROM pg_indexes WHERE schemaname = 'public'"
        )
    )
    by_table: dict[str, list[tuple[tuple[str, ...], bool, str]]] = {}
    for tablename, _indexname, indexdef, is_unique, method in result:
        by_table.setdefault(tablename, []).append((_parse_columns(indexdef), is_unique, method))
    return by_table


@pytest.mark.anyio
async def test_every_documented_index_exists():
    engine = get_engine()
    async with engine.connect() as conn:
        by_table = await _load_indexes(conn)

    missing = []
    for table, expected_indexes in _DOCUMENTED_INDEXES.items():
        actual = by_table.get(table, [])
        for columns, is_unique in expected_indexes:
            found = any(
                actual_columns == columns and (actual_unique == is_unique or not is_unique)
                for actual_columns, actual_unique, _method in actual
            )
            if not found:
                missing.append((table, columns, is_unique))

    assert missing == [], f"{len(missing)} documented index(es) missing: {missing}"


@pytest.mark.anyio
async def test_every_documented_gin_index_exists_with_the_gin_access_method():
    engine = get_engine()
    async with engine.connect() as conn:
        by_table = await _load_indexes(conn)

    missing = []
    for table, columns in _GIN_INDEXES.items():
        actual = by_table.get(table, [])
        for column in columns:
            found = any(actual_columns == (column,) and method == "gin" for actual_columns, _unique, method in actual)
            if not found:
                missing.append((table, column))

    assert missing == [], f"{len(missing)} documented GIN index(es) missing: {missing}"

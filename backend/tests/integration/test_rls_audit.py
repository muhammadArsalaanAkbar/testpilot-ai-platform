"""T202: full RLS policy audit — every tenant table (organization_id NOT
NULL, per data-model.md's blanket rule) must have ROW LEVEL SECURITY
enabled AND forced AND a `tenant_isolation`-style policy scoping it by
`organization_id`; every documented exception must NOT have one. Queries
pg_class/pg_policies directly so this catches drift between what a
migration *should* have done and what's actually live on the schema.
"""

import pytest
from sqlalchemy import text

from testpilot.core.db import get_engine

# Every table data-model.md's blanket rule covers, plus the tables shipped
# ahead of their originally Future-only schedule (assistant_conversations/
# assistant_messages, Phase 15; invitations, T084) -- all built with the
# same standard RLS template from the start specifically so no later
# migration would need to retrofit it.
_TENANT_TABLES = {
    "memberships",
    "projects",
    "test_cases",
    "test_steps",
    "test_runs",
    "test_run_cases",
    "test_results",
    "artifacts",
    "ai_analyses",
    "generation_runs",
    "issues",
    "issue_attachments",
    "notifications",
    "usage_records",
    "assistant_conversations",
    "assistant_messages",
    "invitations",
    "audit_log_entries",  # organization_id nullable, but still RLS'd (audit_read policy) -- see below
}

# data-model.md's explicit exceptions to the blanket rule: no organization_id
# column at all, or organization_id exists but the table is deliberately not
# tenant-isolated by it (organizations *is* the tenant scope; subscription_plans
# is shared catalog data).
_NOT_TENANT_SCOPED = {
    "users",
    "organizations",
    "subscription_plans",
    "refresh_tokens",
    "password_reset_tokens",
    "alembic_version",
}


async def _relrowsecurity(conn) -> dict[str, tuple[bool, bool]]:
    result = await conn.execute(
        text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r'"
        )
    )
    return {row[0]: (row[1], row[2]) for row in result}


async def _policies(conn) -> dict[str, list[tuple[str, str, str | None]]]:
    result = await conn.execute(
        text("SELECT tablename, policyname, cmd, qual FROM pg_policies WHERE schemaname = 'public'")
    )
    by_table: dict[str, list[tuple[str, str, str | None]]] = {}
    for tablename, policyname, cmd, qual in result:
        by_table.setdefault(tablename, []).append((policyname, cmd, qual))
    return by_table


@pytest.mark.anyio
async def test_every_tenant_table_has_rls_enabled_and_forced():
    engine = get_engine()
    async with engine.connect() as conn:
        flags = await _relrowsecurity(conn)

    missing = [table for table in _TENANT_TABLES if flags.get(table) != (True, True)]
    assert missing == [], f"tenant table(s) missing ENABLE+FORCE ROW LEVEL SECURITY: {missing}"


@pytest.mark.anyio
async def test_no_documented_exception_has_rls_enabled():
    """The inverse check: a table that's supposed to be exempt (no
    organization_id, or shared catalog data) must not have RLS turned on
    either -- that would silently hide every row from every request."""
    engine = get_engine()
    async with engine.connect() as conn:
        flags = await _relrowsecurity(conn)

    unexpected = [table for table in _NOT_TENANT_SCOPED if flags.get(table, (False, False)) != (False, False)]
    assert unexpected == [], f"non-tenant table(s) unexpectedly have RLS enabled: {unexpected}"


@pytest.mark.anyio
async def test_every_tenant_table_has_an_organization_scoped_policy():
    engine = get_engine()
    async with engine.connect() as conn:
        policies = await _policies(conn)

    missing = []
    for table in _TENANT_TABLES:
        table_policies = policies.get(table, [])
        # audit_log_entries splits read/insert into two policies (SEC-010:
        # inserts must succeed even from system/no-org-context events, only
        # reads are organization-scoped) -- every other tenant table has one
        # single tenant_isolation policy covering all commands.
        has_org_scoped_policy = any(
            qual is not None and "organization_id" in qual and "current_org_id" in qual
            for _name, _cmd, qual in table_policies
        )
        if not has_org_scoped_policy:
            missing.append(table)

    assert missing == [], f"tenant table(s) with no organization_id-scoped RLS policy: {missing}"


@pytest.mark.anyio
async def test_memberships_policy_also_allows_the_rows_own_user():
    """data-model.md's documented special case: readable by the row's own
    user_id regardless of current_org_id (needed for org-switching)."""
    engine = get_engine()
    async with engine.connect() as conn:
        policies = await _policies(conn)

    quals = [qual for _name, _cmd, qual in policies.get("memberships", []) if qual]
    assert any(qual and "current_user_id" in qual for qual in quals)

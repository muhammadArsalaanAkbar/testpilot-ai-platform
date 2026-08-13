"""create least-privilege app role and RLS policy template, apply to memberships

Revision ID: 0e1c705a31ba
Revises: 85cd22d838b5
Create Date: 2026-08-10 11:29:42.423771

This migration establishes the two-part tenant-isolation mechanism required
by DATA-001/SEC-011 (research.md #4):

1. A dedicated, non-superuser `testpilot_app` Postgres role that the API,
   worker, and CLI connect as at runtime (`Settings.database_url`).
   Row-Level Security policies never apply to a superuser, and — without
   `FORCE ROW LEVEL SECURITY` — never apply to a table's owner either. The
   role that runs migrations (`Settings.migrations_database_url`) owns every
   table it creates, so an RLS policy alone, with the app connecting as that
   same owning role, would silently enforce nothing. `testpilot_app` is
   granted only DML privileges (SELECT/INSERT/UPDATE/DELETE), never DDL or
   ownership, on every table — including tables created by *future*
   migrations, via `ALTER DEFAULT PRIVILEGES` — so this grant does not need
   to be repeated as new domain tables are added in later phases.

2. The reusable RLS policy template: `USING (organization_id =
   current_setting('app.current_org_id', true)::uuid)`, applied here to
   `memberships` per data-model.md's note that `memberships` also needs a
   second, OR'd condition — a member can read their own membership row
   regardless of which Organization is currently selected as
   `app.current_org_id` (needed for the Future org-switching UI). Every
   later domain-table migration that adds Organization-scoped tables MUST
   apply this same template (the plain, single-condition form, unless that
   table has the same "also readable by its own user" need memberships
   has).

The role's password is read from the `APP_DB_PASSWORD` environment variable
at migration time so it is never hardcoded; the dev-only fallback below
matches the value already used in backend/.env for local development and
MUST be overridden (via real secrets management, not this file) in any
shared environment.
"""
import os
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e1c705a31ba"
down_revision: str | Sequence[str] | None = "85cd22d838b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "testpilot_app"
_DEV_ONLY_DEFAULT_PASSWORD = "testpilot_app_dev_only_password"  # noqa: S105 - local dev fallback only


def upgrade() -> None:
    password = os.environ.get("APP_DB_PASSWORD", _DEV_ONLY_DEFAULT_PASSWORD)

    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
            CREATE ROLE {_APP_ROLE} WITH LOGIN PASSWORD '{password}';
          ELSE
            ALTER ROLE {_APP_ROLE} WITH LOGIN PASSWORD '{password}';
          END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {_APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_APP_ROLE}")
    # Applies to tables created by migrations that run after this one, so
    # this grant never needs to be repeated as new domain tables are added.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {_APP_ROLE}"
    )

    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON memberships
        USING (
            organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
            OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON memberships")
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {_APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {_APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {_APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {_APP_ROLE}")

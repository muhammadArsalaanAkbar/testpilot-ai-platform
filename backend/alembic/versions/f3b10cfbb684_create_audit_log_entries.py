"""create audit_log_entries

Revision ID: f3b10cfbb684
Revises: c828fd4bd7d5
Create Date: 2026-08-10 12:01:02.708142

Deliberately does not use the standard tenant-table RLS template (see
core/models.py / the rls_role_and_policies migration): `organization_id` is
nullable here (data-model.md lists this table as an explicit exception), and
a single USING-only policy would also gate INSERTs via its implicit WITH
CHECK — but audit writes must succeed even with no established tenant
context (e.g. a failed-login attempt from an unauthenticated request has no
app.current_org_id set at all). So this table gets two separate policies:
SELECT is Organization-scoped (for the Future FR-129 read endpoint), INSERT
is unconditionally permitted (trusted, internal application code is the only
writer — audit/service.py — not tenant-supplied data).
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3b10cfbb684'
down_revision: str | Sequence[str] | None = 'c828fd4bd7d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('audit_log_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('resource_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('resource_id', sa.Uuid(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # Composite indexes per data-model.md, not the single-column indexes
    # SQLModel's Field(index=True) would generate on its own.
    op.create_index(
        "ix_audit_log_entries_org_created_at",
        "audit_log_entries",
        ["organization_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_log_entries_actor_created_at",
        "audit_log_entries",
        ["actor_user_id", sa.text("created_at DESC")],
    )

    op.execute("ALTER TABLE audit_log_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_read ON audit_log_entries
        FOR SELECT
        USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
        """
    )
    op.execute("CREATE POLICY audit_insert ON audit_log_entries FOR INSERT WITH CHECK (true)")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_insert ON audit_log_entries")
    op.execute("DROP POLICY IF EXISTS audit_read ON audit_log_entries")
    op.execute("ALTER TABLE audit_log_entries NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log_entries DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_audit_log_entries_actor_created_at", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_org_created_at", table_name="audit_log_entries")
    op.drop_table('audit_log_entries')

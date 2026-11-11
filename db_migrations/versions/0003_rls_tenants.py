"""RLS on tenants; app role loses access to system-only tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 19:10:00

Defense in depth: the app role sees only its own tenant row (it may create a tenant only while the RLS
context already names that new tenant id) and cannot touch migration/system bookkeeping tables.
"""
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

ROLE = "application_user"
SETTING = "app.current_tenant_id"
SYSTEM_ONLY = ["alembic_version"]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    cur = f"NULLIF(current_setting('{SETTING}', true), '')::uuid"
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_self ON tenants")
    op.execute(f"CREATE POLICY tenant_self ON tenants FOR ALL TO {ROLE} USING (id = {cur}) WITH CHECK (id = {cur})")
    for table in SYSTEM_ONLY:
        op.execute(f"REVOKE ALL ON {table} FROM {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS tenant_self ON tenants")
    op.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
    for table in SYSTEM_ONLY:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {ROLE}")

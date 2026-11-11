"""row-level security: app role without BYPASSRLS, tenant policies, append-only audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11 18:30:00

The application connects as `application_user` (no owner rights, no BYPASSRLS). Give it a password and LOGIN
once per environment:  ALTER ROLE application_user LOGIN PASSWORD '...';
"""
from pathlib import Path

from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

ROLE = "application_user"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN CREATE ROLE {ROLE} NOLOGIN; END IF;
    END $$""")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE}")
    for stmt in _statements((Path(__file__).resolve().parents[1] / "001_rls.sql").read_text()):
        op.execute(stmt)


def _statements(sql: str) -> list[str]:
    """Split a script into single statements (asyncpg runs one per call), respecting \$\$-quoted bodies."""
    out, buf, in_dollar = [], [], False
    for line in sql.splitlines():
        if line.strip().startswith("--") and not in_dollar:
            continue
        buf.append(line)
        in_dollar ^= line.count("$$") % 2 == 1
        if not in_dollar and line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";")
            if stmt:
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";")
    if tail:
        out.append(tail)
    return out


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE}")

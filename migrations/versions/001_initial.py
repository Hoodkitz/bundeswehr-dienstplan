"""Initial migration for Bundeswehr Dienstplan."""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'tenants',
        sa.Column('id', sa.UUID, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('security_classification', sa.String(50), default='VS-NfD'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        'soldat',
        sa.Column('id', sa.UUID, primary_key=True),
        sa.Column('tenant_id', sa.UUID, sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('personalnummer', sa.String(50), nullable=False),
        sa.Column('dienstgrad', sa.String(50), nullable=False),
        sa.Column('vorname', sa.String(100), nullable=False),
        sa.Column('nachname', sa.String(100), nullable=False),
        sa.Column('qualifikationen', sa.JSON, default=[]),
    )
    op.create_table(
        'dienstplan',
        sa.Column('id', sa.UUID, primary_key=True),
        sa.Column('tenant_id', sa.UUID, sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('planungszeitraum_start', sa.Date, nullable=False),
        sa.Column('planungszeitraum_ende', sa.Date, nullable=False),
        sa.Column('status', sa.String(50), default='DRAFT_INIT'),
        sa.Column('approver_id', sa.UUID, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    # Enable RLS
    op.execute('ALTER TABLE soldat ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE soldat FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE dienstplan ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE dienstplan FORCE ROW LEVEL SECURITY')

def downgrade():
    op.drop_table('dienstplan')
    op.drop_table('soldat')
    op.drop_table('tenants')

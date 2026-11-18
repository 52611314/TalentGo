"""Persist primary and secondary training targets in profiles."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006_profile_secondary_roles'
down_revision = '0005_accounts_roles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('profiles', sa.Column('secondary_roles', postgresql.JSONB(), nullable=False,
                                      server_default=sa.text("'[]'::jsonb")))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM profiles WHERE secondary_roles <> '[]'::jsonb)")).scalar():
        raise RuntimeError('Saved secondary targets exist; preserve their data before downgrading')
    op.drop_column('profiles', 'secondary_roles')

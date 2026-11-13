"""M1: anonymous identities, profiles and synchronous request receipts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_m1_foundation'
down_revision = None
branch_labels = None
depends_on = None


def common_columns():
    return [sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table('users', *common_columns(),
        sa.Column('display_name', sa.String(60), nullable=False),
        sa.Column('token_hash', sa.String(128), nullable=False),
        sa.Column('creation_key_hash', sa.String(128), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_users'),
        sa.UniqueConstraint('token_hash', name='uq_users_token_hash'),
        sa.UniqueConstraint('creation_key_hash', name='uq_users_creation_key_hash'),
        sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_users_status'))
    op.create_table('profiles', *common_columns(),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('target_role', sa.String(32), nullable=True),
        sa.Column('experience_level', sa.String(24), nullable=True),
        sa.Column('tech_stack', postgresql.JSONB(), nullable=False),
        sa.Column('background', sa.Text(), nullable=False),
        sa.Column('goals', sa.Text(), nullable=False),
        sa.Column('feedback_style', sa.String(24), nullable=False),
        sa.Column('allow_inferred_memory', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('memory_revision', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_profiles'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_profiles_user_id_users', ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_profiles_user_id'),
        sa.CheckConstraint("target_role IS NULL OR target_role IN ('frontend', 'backend')", name='ck_profiles_role'),
        sa.CheckConstraint("experience_level IS NULL OR experience_level IN ('beginner', 'intern', 'graduate')", name='ck_profiles_level'),
        sa.CheckConstraint("feedback_style IN ('concise', 'detailed', 'guided')", name='ck_profiles_feedback_style'),
        sa.CheckConstraint('version > 0 AND memory_revision > 0', name='ck_profiles_versions'))
    op.create_table('idempotency_receipts', *common_columns(),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('key_hash', sa.String(128), nullable=False),
        sa.Column('request_hash', sa.String(128), nullable=False),
        sa.Column('response_data', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_idempotency_receipts'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_idempotency_receipts_user_id_users', ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'key_hash', name='uq_idempotency_receipts_user_id'))


def downgrade():
    op.drop_table('idempotency_receipts')
    op.drop_table('profiles')
    op.drop_table('users')

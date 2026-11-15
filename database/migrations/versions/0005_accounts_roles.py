"""Accounts and extensible target roles; retain pre-account user data."""
from alembic import op
import sqlalchemy as sa

revision = '0005_accounts_roles'
down_revision = '0004_m4_memory'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('username', sa.String(32), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(256), nullable=True))
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.create_table('auth_sessions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(128), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.drop_constraint(op.f('ck_profiles_ck_profiles_role'), 'profiles', type_='check')
    op.drop_constraint(op.f('ck_interview_sessions_role'), 'interview_sessions', type_='check')


def downgrade():
    # Do not silently destroy accounts or coerce newly supported roles.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS(SELECT 1 FROM users WHERE username IS NOT NULL) OR EXISTS(SELECT 1 FROM profiles WHERE target_role NOT IN ('frontend','backend')) OR EXISTS(SELECT 1 FROM interview_sessions WHERE role NOT IN ('frontend','backend'))")).scalar():
        raise RuntimeError('Accounts/new roles exist; export and migrate their data before downgrading')
    op.create_check_constraint(op.f('ck_profiles_ck_profiles_role'), 'profiles', "target_role IS NULL OR target_role IN ('frontend','backend')")
    op.create_check_constraint(op.f('ck_interview_sessions_role'), 'interview_sessions', "role IS NULL OR role IN ('frontend','backend')")
    op.drop_table('auth_sessions')
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')

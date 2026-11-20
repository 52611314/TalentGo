"""Store question timers across refresh and pause/resume."""
from alembic import op
import sqlalchemy as sa

revision = '0007_question_answer_clock'
down_revision = '0006_profile_secondary_roles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('questions', sa.Column('answer_deadline_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('questions', sa.Column('answer_remaining_ms', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('questions', 'answer_remaining_ms')
    op.drop_column('questions', 'answer_deadline_at')

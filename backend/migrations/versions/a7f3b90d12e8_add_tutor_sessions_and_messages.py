"""add_tutor_sessions_and_messages

Revision ID: a7f3b90d12e8
Revises: 5d7e502760f4
Create Date: 2026-10-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a7f3b90d12e8'
down_revision: Union[str, None] = '5d7e502760f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tutor_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resource_id'], ['learning_resources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'resource_id'),
    )
    op.create_index('ix_tutor_sessions_user_id', 'tutor_sessions', ['user_id'])
    op.create_index('ix_tutor_sessions_resource_id', 'tutor_sessions', ['resource_id'])

    op.create_table(
        'tutor_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['tutor_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tutor_messages_session_id', 'tutor_messages', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_tutor_messages_session_id', table_name='tutor_messages')
    op.drop_table('tutor_messages')
    op.drop_index('ix_tutor_sessions_resource_id', table_name='tutor_sessions')
    op.drop_index('ix_tutor_sessions_user_id', table_name='tutor_sessions')
    op.drop_table('tutor_sessions')

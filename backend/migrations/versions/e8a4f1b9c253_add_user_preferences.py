"""add_user_preferences

Revision ID: e8a4f1b9c253
Revises: 4df931a7000b
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e8a4f1b9c253'
down_revision: Union[str, None] = '4df931a7000b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'preferences')

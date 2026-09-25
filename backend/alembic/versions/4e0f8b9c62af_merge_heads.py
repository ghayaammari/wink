"""merge heads

Revision ID: 4e0f8b9c62af
Revises: 94c021097c6d, acb040c7128a
Create Date: 2026-09-23 11:05:05.339802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e0f8b9c62af'
down_revision: Union[str, Sequence[str], None] = ('94c021097c6d', 'acb040c7128a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

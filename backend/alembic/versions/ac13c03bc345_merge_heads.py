"""merge heads

Revision ID: ac13c03bc345
Revises: 4e0f8b9c62af
Create Date: 2026-09-23 11:47:20.209146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac13c03bc345'
down_revision: Union[str, Sequence[str], None] = '4e0f8b9c62af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

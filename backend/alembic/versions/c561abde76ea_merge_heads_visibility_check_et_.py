"""merge heads visibility_check et investor_completion_check

Revision ID: c561abde76ea
Revises: 82a64157b35d, a1b2c3d4e5f6
Create Date: 2026-09-08 20:47:46.249244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c561abde76ea'
down_revision: Union[str, Sequence[str], None] = ('82a64157b35d', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

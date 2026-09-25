"""merge heads

Revision ID: 94c021097c6d
Revises: aced0deef1e7
Create Date: 2026-09-23 10:45:22.882355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94c021097c6d'
down_revision: Union[str, Sequence[str], None] = 'aced0deef1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

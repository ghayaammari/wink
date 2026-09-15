"""add notifications (service 1.1.9, Groupe 4)

Revision ID: bc9bc60d56ea
Revises: 0381359114ec
Create Date: 2026-09-12 16:00:00.000000

Table générique — pas propre au Kbis, réutilisable par toute future
notification projet. Premier usage : service 1.1.9 (notification de
disponibilité du Kbis, Parcours A).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bc9bc60d56ea'
down_revision: Union[str, Sequence[str], None] = '0381359114ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('node_id_suivant', sa.String(length=100), nullable=True),
        sa.Column('lue', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id_suivant'], ['roadmap_nodes.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('notifications')

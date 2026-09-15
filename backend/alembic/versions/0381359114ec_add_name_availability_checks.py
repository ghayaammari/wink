"""add name_availability_checks (service 1.1.2, Groupe 4)

Revision ID: 0381359114ec
Revises: 4fa5a487a845
Create Date: 2026-09-12 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0381359114ec'
down_revision: Union[str, Sequence[str], None] = '4fa5a487a845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'name_availability_checks',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('nom_teste', sa.String(length=255), nullable=False),
        sa.Column('statut_denomination', sa.String(length=20), nullable=False),
        sa.Column('statut_marque', sa.String(length=20), nullable=False),
        sa.Column('verifie_le', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "statut_denomination IN ('disponible', 'pris')",
            name='ck_name_availability_checks_statut_denomination',
        ),
        sa.CheckConstraint(
            "statut_marque IN ('disponible', 'risque', 'pris')",
            name='ck_name_availability_checks_statut_marque',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('name_availability_checks')

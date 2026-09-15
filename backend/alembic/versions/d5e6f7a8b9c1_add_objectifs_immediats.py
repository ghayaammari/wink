"""add objectifs_immediats to projects (service 1.1.11 — condition e23_depot_marque)

Revision ID: d5e6f7a8b9c1
Revises: bc9bc60d56ea
Create Date: 2026-09-14 18:00:00.000000

Colonne liste des objectifs immédiats déclarés par l'entrepreneur (ex:
"protection_marque_code"), réponse à une question posée à l'onboarding (écran
"Équipe et ambitions"). Sert au filtrage de la roadmap par projet (service
1.1.11, condition applicable_if de e23_depot_marque). Réalisé par OPENCODE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c1'
down_revision: Union[str, Sequence[str], None] = 'bc9bc60d56ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column(
            'objectifs_immediats',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'objectifs_immediats')
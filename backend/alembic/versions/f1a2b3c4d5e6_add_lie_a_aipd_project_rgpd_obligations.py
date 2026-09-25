"""add lie_a_aipd to project_rgpd_obligations (service 3.3.1 / 3.3.4)

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-17 00:00:00.000000

Ajoute un booleen `lie_a_aipd` sur `project_rgpd_obligations` et sa table
d'archivage `project_rgpd_obligations_history`, pour permettre au frontend
de regrouper a part les obligations liees a une AIPD (demande explicite,
voir echange du 17/09/2026). Booleen plutot qu'une categorie/enum a plusieurs
valeurs : voir docstring de project_rgpd_obligation.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'project_rgpd_obligations',
        sa.Column('lie_a_aipd', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'project_rgpd_obligations_history',
        sa.Column('lie_a_aipd', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('project_rgpd_obligations_history', 'lie_a_aipd')
    op.drop_column('project_rgpd_obligations', 'lie_a_aipd')

"""convert sector_insurance_recommendations.secteur (scalar) to secteurs (array)

Revision ID: c2e7f4b8a913
Revises: b4f9d2a1c6e3
Create Date: 2026-09-11 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2e7f4b8a913'
down_revision: Union[str, Sequence[str], None] = 'b4f9d2a1c6e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IMPORTANT : cette table ne contient que des donnees de test jetables
    # (collecte partielle, 2 blocs sur 7). Pas de tentative de conversion
    # ligne par ligne (regrouper les N lignes d'un meme article en 1 seule
    # avec secteurs=array n'est pas trivial et ne vaut pas l'effort pour des
    # donnees jetables) : on vide la table, le script de collecte est
    # idempotent et relancable sans re-payer le cout LLM sur les articles
    # deja connus dans legal_texts (voir get_legal_text() / skip dans
    # collect_sector_insurance_recommendations.py).
    op.execute("TRUNCATE TABLE sector_insurance_recommendations")

    op.drop_constraint(
        'uq_sector_insurance_legal_text_secteur', 'sector_insurance_recommendations', type_='unique'
    )
    op.drop_column('sector_insurance_recommendations', 'secteur')
    op.add_column(
        'sector_insurance_recommendations',
        sa.Column(
            'secteurs',
            sa.dialects.postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_unique_constraint(
        'uq_sector_insurance_legal_text',
        'sector_insurance_recommendations',
        ['legal_text_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_sector_insurance_legal_text', 'sector_insurance_recommendations', type_='unique'
    )
    op.drop_column('sector_insurance_recommendations', 'secteurs')
    op.add_column(
        'sector_insurance_recommendations',
        sa.Column('secteur', sa.String(120), nullable=False, server_default=''),
    )
    op.create_unique_constraint(
        'uq_sector_insurance_legal_text_secteur',
        'sector_insurance_recommendations',
        ['legal_text_id', 'secteur'],
    )

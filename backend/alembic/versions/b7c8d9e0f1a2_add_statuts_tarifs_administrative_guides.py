"""extend administrative_guides.domaine with statuts/tarifs

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-24 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute 'statuts' et 'tarifs' aux domaines acceptes par
    administrative_guides -- deja acceptes par content_embeddings.domaine
    depuis la migration 6f1a2c9d3e5b, aucun changement necessaire de ce
    cote."""
    op.drop_constraint('ck_administrative_guides_domaine', 'administrative_guides', type_='check')
    op.create_check_constraint(
        'ck_administrative_guides_domaine',
        'administrative_guides',
        "domaine IN ('pacte_fondateurs', 'pre_depot', 'statuts', 'tarifs', 'annonce_legale')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_administrative_guides_domaine', 'administrative_guides', type_='check')
    op.create_check_constraint(
        'ck_administrative_guides_domaine',
        'administrative_guides',
        "domaine IN ('pacte_fondateurs', 'pre_depot')",
    )

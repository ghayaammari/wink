"""add forme_juridique/statuts_societe to content_embeddings domaine check

Revision ID: 6f1a2c9d3e5b
Revises: 0d4f6f0e508e
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6f1a2c9d3e5b'
down_revision: Union[str, Sequence[str], None] = '0d4f6f0e508e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Préalable à la Phase 3 (embedding) du service 1.1.1 : la contrainte
    d'origine (migration d44de64699d4) n'autorisait pas encore 'forme_juridique'
    ni 'statuts_societe' (mêmes valeurs que legal_texts.domaine_reglementaire,
    voir blocs_formes_juridiques.py) — sans cette migration, toute insertion
    dans content_embeddings pour une source legal_texts échoue."""
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap')",
    )

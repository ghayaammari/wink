"""add ai_act domaine on content_embeddings

Revision ID: e2c4a6b8d0f1
Revises: a3f8e2c1b9d4
Create Date: 2026-09-19 00:00:00.000000

Service 3.3.12 (AI Act) — legal_texts n'a besoin d'aucune migration
(domaine_reglementaire et sous_theme sont des colonnes String libres, sans
CheckConstraint, voir legal_texts.py). Seule content_embeddings.domaine est
verrouillee par une CheckConstraint (verifiee au moment de l'embedding, voir
chunk_and_embed_legal_texts.py) : meme demarche que d3a9f21c6b48 pour 'rgpd'
et a7b3c8d1e4f2 pour 'assurance_sectorielle', on y ajoute 'ai_act'.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2c4a6b8d0f1'
down_revision: Union[str, Sequence[str], None] = 'a3f8e2c1b9d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd', 'ai_act')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd')",
    )

"""add type_source to legal_texts + rgpd domaine on content_embeddings

Revision ID: d3a9f21c6b48
Revises: f7b1c2d3e4f6
Create Date: 2026-09-16 00:00:00.000000

Service 3.3.1 (RGPD) — legal_texts contenait jusqu'ici uniquement des
articles de loi (service 1.1.1). Le RGPD y ajoute des guides CNIL (HTML) et
un guide PDF, pas des articles de loi a proprement parler : `type_source`
distingue ces cas sans dupliquer les colonnes (texte_brut/source_url/
domaine_reglementaire s'appliquent identiquement aux deux, voir decision du
15/09/2026 — pas de table separee `legal_guides`).

`article_loi` reste la valeur par defaut (server_default) pour ne pas
retoucher les lignes deja collectees (service 1.1.1, 1.1.10) : elles sont
toutes des articles de loi.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3a9f21c6b48'
down_revision: Union[str, Sequence[str], None] = 'f7b1c2d3e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. type_source sur legal_texts
    op.add_column(
        'legal_texts',
        sa.Column('type_source', sa.String(20), nullable=False, server_default='article_loi'),
    )
    op.create_check_constraint(
        'ck_legal_texts_type_source',
        'legal_texts',
        "type_source IN ('article_loi', 'guide_pratique', 'faq', 'pdf')",
    )

    # 2. Elargir la contrainte de domaine sur content_embeddings pour accepter
    # 'rgpd' (meme demarche que a7b3c8d1e4f2 pour 'assurance_sectorielle').
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle')",
    )

    op.drop_constraint('ck_legal_texts_type_source', 'legal_texts', type_='check')
    op.drop_column('legal_texts', 'type_source')

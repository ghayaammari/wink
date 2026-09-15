"""add sector_insurance_recommendations table and assurance_sectorielle domain

Revision ID: a7b3c8d1e4f2
Revises: 6f1a2c9d3e5b
Create Date: 2026-09-11 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b3c8d1e4f2'
down_revision: Union[str, Sequence[str], None] = '6f1a2c9d3e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Creer la table sector_insurance_recommendations
    op.create_table(
        'sector_insurance_recommendations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('secteur', sa.String(120), nullable=False),
        sa.Column('type_assurance', sa.String(120), nullable=False),
        sa.Column('a_base_legale', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('legal_text_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('legal_texts.id'), nullable=True),
        sa.Column('source_nom', sa.String(255), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('texte_brut', sa.Text(), nullable=True),
        sa.Column('statut_contenu', sa.String(20), nullable=False, server_default='extrait_automatique'),
        sa.Column('collecte_le', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('derniere_verification', sa.Date(), nullable=True),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name='ck_sector_insurance_statut_contenu',
        ),
    )

    # 2. Elargir la contrainte de domaine sur content_embeddings pour accepter
    # 'assurance_sectorielle' (anticipe par le commentaire dans content_embeddings.py :
    # "a etendre explicitement quand un nouveau source_type/domaine est introduit").
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle')",
    )


def downgrade() -> None:
    # Restaurer la contrainte sans 'assurance_sectorielle'
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe')",
    )

    op.drop_table('sector_insurance_recommendations')

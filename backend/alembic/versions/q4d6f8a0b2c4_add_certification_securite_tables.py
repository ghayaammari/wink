"""add certification_secnumcloud domaine + tables (service 3.3.11)

Revision ID: q4d6f8a0b2c4
Revises: n1b3c5d7e9f1
Create Date: 2026-09-21 00:00:00.000000

Service 3.3.11 (Accompagnement accéléré vers les certifications de sécurité).
V1 volontairement restreinte à SecNumCloud (décision produit) : seule des 3
certifications visées à terme (ISO 27001, SOC 2, SecNumCloud) dont le
référentiel est entièrement public (ANSSI, PDF librement téléchargeable) --
un vrai scraping est possible dès cette V1, contrairement à ISO 27001/SOC 2
dont le texte complet est payant/propriétaire (voir discussion produit).
SecNumCloud couvre par ailleurs le volet "vendre à l'État" du besoin
(exigé par les marchés publics/OIV), distinct du volet "grands comptes
privés" qui vise plutôt ISO 27001.

Même démarche que h5c7d9e1f3a5 (secteur_fintech/secteur_healthtech) :
content_embeddings.domaine est verrouillée par une CheckConstraint, on y
ajoute le nouveau domaine 'certification_secnumcloud'.

`type_certification` (colonne, pas une table par certification) sur les 2
tables ci-dessous, avec une CheckConstraint limitée à 'secnumcloud' pour
l'instant : ISO 27001/SOC 2 s'ajouteront plus tard en étendant cette
CheckConstraint (comme domaine l'a déjà été 6 fois dans ce projet), jamais
en recréant une table -- coût nul aujourd'hui, évite une vraie migration
structurelle quand ces 2 certifications seront construites.

2 tables, même pattern que project_rgpd_obligations / compliance_score
(voir e5f6a7b8c9d0) :
- project_certification_obligations : étapes du parcours de certification,
  une ligne par étape, statut coché manuellement par l'entrepreneur (jamais
  écrasé par une régénération -- logique portée par le service, comme RGPD).
  `ordre` en plus de RGPD : contrairement aux obligations RGPD (recensées
  sans ordre particulier), les étapes d'une certification suivent un
  parcours séquentiel réel (ex: gap analysis avant audit blanc avant audit
  de certification).
- project_certification_estimations : délai/coût estimé pour un couple
  (projet, type de certification) -- 1 ligne par type de certification déjà
  généré pour ce projet, jamais recalculée automatiquement (régénération
  explicite seulement, même logique que les autres domaines).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'q4d6f8a0b2c4'
down_revision: Union[str, Sequence[str], None] = 'n1b3c5d7e9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TYPE_CERTIFICATION_CHECK = "type_certification IN ('secnumcloud')"


def upgrade() -> None:
    # 1. Nouveau domaine content_embeddings
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd', 'ai_act', 'secteur_fintech', 'secteur_healthtech', "
        "'certification_secnumcloud')",
    )

    # 2. project_certification_obligations
    op.create_table(
        'project_certification_obligations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type_certification', sa.String(20), nullable=False),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('statut', sa.String(20), server_default='a_faire', nullable=False),
        sa.Column('legal_text_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['legal_text_id'], ['legal_texts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id', 'type_certification', 'nom', name='uq_project_certification_obligations_project_type_nom'
        ),
        sa.CheckConstraint(_TYPE_CERTIFICATION_CHECK, name='ck_project_certification_obligations_type'),
        sa.CheckConstraint("statut IN ('a_faire', 'fait')", name='ck_project_certification_obligations_statut'),
    )

    # 3. project_certification_estimations
    op.create_table(
        'project_certification_estimations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type_certification', sa.String(20), nullable=False),
        sa.Column('delai_mois_min', sa.Integer(), nullable=False),
        sa.Column('delai_mois_max', sa.Integer(), nullable=False),
        sa.Column('cout_estime_min', sa.Integer(), nullable=False),
        sa.Column('cout_estime_max', sa.Integer(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id', 'type_certification', name='uq_project_certification_estimations_project_type'
        ),
        sa.CheckConstraint(_TYPE_CERTIFICATION_CHECK, name='ck_project_certification_estimations_type'),
    )


def downgrade() -> None:
    op.drop_table('project_certification_estimations')
    op.drop_table('project_certification_obligations')
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd', 'ai_act', 'secteur_fintech', 'secteur_healthtech')",
    )

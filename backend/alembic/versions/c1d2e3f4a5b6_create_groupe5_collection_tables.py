"""create Groupe 5 collection tables (contract clauses library + templates)

Services 1.1.13 (pacte de fondateurs) / 1.1.4 (statuts) — Phase collecte,
Groupe 5, Incrément 1. Voir Groupe5_doc.md et "Wink — Schémas Incrément 1 v3".

Trois nouvelles tables de contenu de référence externe, sous
backend/shared/knowledge_base/ (même famille que legal_texts/content_embeddings :
corpus alimenté par pipelines de collecte, pas par saisie projet) :
- contract_clauses_library : une clause type par ligne (texte template + champs
  d'intention), socle partagé pacte/statuts/(futurs nda,cession_ip) ;
- clause_validity_criteria : critères de conformité par clause, NON vectorisés,
  lus par jointure directe, seuils détectés par code déterministe ;
- document_templates : squelette ordonné des sections d'un document, pointe vers
  legal_texts ou contract_clauses_library (référence polymorphe, pas de FK).

Pas de CHECK sur contract_clauses_library.document_type : liste évolutive
(nda/cession_ip en I2), on la fige quand le besoin arrive.
(réalisé par OPENCODE)

Revision ID: c1d2e3f4a5b6
Revises: d2e3f4a5b6c7
Create Date: 2026-09-15 09:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- contract_clauses_library ---  # (réalisé par OPENCODE)
    op.create_table(
        'contract_clauses_library',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('document_type', sa.String(40), nullable=False),
        sa.Column('scenario', sa.String(80), nullable=False),
        sa.Column('scenario_description', sa.Text(), nullable=False),
        sa.Column('titre_clause', sa.String(255), nullable=False),
        sa.Column('texte_clause', sa.Text(), nullable=False),
        sa.Column('variables_requises', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('source_modele', sa.String(120), nullable=False),
        sa.Column('verifie_par_professionnel', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('forme_juridique_concernee', sa.String(60), nullable=True),
        sa.Column('collecte_le', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('derniere_verification', sa.Date(), nullable=True),
        sa.Column('statut_contenu', sa.String(20), nullable=False, server_default='extrait_automatique'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name='ck_contract_clauses_library_statut_contenu',
        ),
    )

    # --- clause_validity_criteria ---  # (réalisé par OPENCODE)
    op.create_table(
        'clause_validity_criteria',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('clause_library_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contract_clauses_library.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type_critere', sa.String(80), nullable=False),
        sa.Column('description_critere', sa.Text(), nullable=False),
        sa.Column('valeur_limite', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('base_legale', sa.Text(), nullable=False),
        sa.Column('statut_contenu', sa.String(20), nullable=False, server_default='extrait_automatique'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name='ck_clause_validity_criteria_statut_contenu',
        ),
    )
    op.create_index('ix_clause_validity_criteria_clause_library_id', 'clause_validity_criteria', ['clause_library_id'])

    # --- document_templates ---  # (réalisé par OPENCODE)
    op.create_table(
        'document_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('document_type', sa.String(40), nullable=False),
        sa.Column('nom_section', sa.String(255), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('type_contenu', sa.String(40), nullable=False),
        sa.Column('reference_type', sa.String(40), nullable=True),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('obligatoire', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('forme_juridique_concernee', sa.String(60), nullable=True),
        sa.Column('texte_statique', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_type', 'ordre', name='uq_document_templates_type_ordre'),
        sa.CheckConstraint(
            "type_contenu IN ('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', 'texte_statique')",
            name='ck_document_templates_type_contenu',
        ),
        sa.CheckConstraint(
            "reference_type IN ('legal_texts', 'contract_clauses_library')",
            name='ck_document_templates_reference_type',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('document_templates')
    op.drop_index('ix_clause_validity_criteria_clause_library_id', table_name='clause_validity_criteria')
    op.drop_table('clause_validity_criteria')
    op.drop_table('contract_clauses_library')
"""add document_generation_sessions + document_templates.variante_obligatoire

Service 1.1.13 (Pacte de fondateurs interactif) — Phase mécanisme, Groupe 5,
Incrément 1. Comble un trou du schéma spécifié : Groupe5_doc.md ne documentait
une "Phase mécanisme" que pour 1.1.6/1.1.5/1.1.7/1.1.8, jamais pour 1.1.13/1.1.4.
Décision actée avec l'utilisateur le 20/09/2026 (voir docstring du modèle
DocumentGenerationSession) : nouvelle table dédiée plutôt que de détourner
project_field_values.

Deuxième changement, nécessaire pour le même service : le template Bpifrance
contient des articles à choix obligatoire entre plusieurs clauses mutuellement
exclusives (ex: Article 3, 7 hypothèses de préemption/préférence — une seule
s'applique, ce n'est ni "obligatoire fixe" ni "optionnelle inclus/exclus").
document_templates.type_contenu ('mention_obligatoire' / 'clause_optionnelle' /
'donnee_projet' / 'texte_statique') ne couvre pas ce cas — ajout de la valeur
'variante_obligatoire'. reference_id reste NULL pour ces lignes : les clauses
candidates ne sont pas une réference unique mais un groupe (résolu par le
service applicatif via un préfixe de `contract_clauses_library.scenario`,
pas par une nouvelle colonne de regroupement en base — décision de ne pas
complexifier contract_clauses_library, qui correspond déjà exactement au
schéma spécifié).

Revision ID: e4a8f1c9b2d7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-20 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4a8f1c9b2d7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- document_generation_sessions (nouvelle) ---
    op.create_table(
        'document_generation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_type', sa.String(40), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='en_cours'),
        sa.Column('section_courante', sa.String(255), nullable=True),
        sa.Column('reponses', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('document_genere_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'document_type', name='uq_document_generation_sessions_project_type'),
        sa.CheckConstraint("statut IN ('en_cours', 'complete')", name='ck_document_generation_sessions_statut'),
    )
    op.create_index('ix_document_generation_sessions_project_id', 'document_generation_sessions', ['project_id'])

    # --- document_templates : extension de type_contenu ---
    op.drop_constraint('ck_document_templates_type_contenu', 'document_templates', type_='check')
    op.create_check_constraint(
        'ck_document_templates_type_contenu',
        'document_templates',
        "type_contenu IN ('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', "
        "'texte_statique', 'variante_obligatoire')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_document_templates_type_contenu', 'document_templates', type_='check')
    op.create_check_constraint(
        'ck_document_templates_type_contenu',
        'document_templates',
        "type_contenu IN ('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', 'texte_statique')",
    )

    op.drop_index('ix_document_generation_sessions_project_id', table_name='document_generation_sessions')
    op.drop_table('document_generation_sessions')

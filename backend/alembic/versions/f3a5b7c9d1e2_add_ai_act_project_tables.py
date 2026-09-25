"""add ai act project tables (service 3.3.12)

Revision ID: f3a5b7c9d1e2
Revises: e2c4a6b8d0f1
Create Date: 2026-09-19 00:00:00.000000

Service 3.3.12 (AI Act) — 4 tables cote projet, miroir du pattern RGPD
(compliance_data_profile / project_rgpd_obligations / _history), plus une
table de classification propre a l'AI Act (voir docstring de
project_ai_act_classification.py pour le raisonnement de separation).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'f3a5b7c9d1e2'
down_revision: Union[str, Sequence[str], None] = 'e2c4a6b8d0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_act_data_profile',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('utilise_ia', sa.Boolean(), nullable=True),
        sa.Column('usage_biometrie_ou_identification', sa.Boolean(), nullable=True),
        sa.Column('usage_scoring_emploi_credit_ou_education', sa.Boolean(), nullable=True),
        sa.Column('usage_infrastructure_ou_securite_critique', sa.Boolean(), nullable=True),
        sa.Column('interagit_ou_genere_contenu_pour_utilisateurs', sa.Boolean(), nullable=True),
        sa.Column('developpe_modele_ia_usage_general', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_ai_act_data_profile_project_id'),
    )

    op.create_table(
        'project_ai_act_classification',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('categorie_risque', sa.Text(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_project_ai_act_classification_project_id'),
        sa.CheckConstraint(
            "categorie_risque IN ('interdit', 'haut_risque', 'risque_limite', 'gouvernance_gpai', 'minimal')",
            name='ck_project_ai_act_classification_categorie_risque',
        ),
    )

    op.create_table(
        'project_ai_act_obligations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='a_faire'),
        sa.Column('legal_text_id', UUID(as_uuid=True), sa.ForeignKey('legal_texts.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'nom', name='uq_project_ai_act_obligations_project_nom'),
        sa.CheckConstraint("statut IN ('a_faire', 'fait')", name='ck_project_ai_act_obligations_statut'),
    )

    op.create_table(
        'project_ai_act_obligations_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("statut IN ('a_faire', 'fait')", name='ck_project_ai_act_obligations_history_statut'),
    )


def downgrade() -> None:
    op.drop_table('project_ai_act_obligations_history')
    op.drop_table('project_ai_act_obligations')
    op.drop_table('project_ai_act_classification')
    op.drop_table('ai_act_data_profile')

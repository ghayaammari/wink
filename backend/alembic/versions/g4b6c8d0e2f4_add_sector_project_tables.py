"""add sector compliance project tables (service 3.3.5)

Revision ID: g4b6c8d0e2f4
Revises: f3a5b7c9d1e2
Create Date: 2026-09-19 00:00:00.000000

Service 3.3.5 (Diagnostic de classification reglementaire) — scope limite a
2 secteurs (HealthTech, FinTech), voir docstring project_sector_detection.py.
5 tables : 1 detection de secteur (etape 0, LLM) + 2 profils tri-etat + 2
classifications (calcul deterministe Python, voir docstring
project_healthtech_classification.py et project_fintech_classification.py).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'g4b6c8d0e2f4'
down_revision: Union[str, Sequence[str], None] = 'f3a5b7c9d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_sector_detection',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('secteur_detecte', sa.Text(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_project_sector_detection_project_id'),
        sa.CheckConstraint(
            "secteur_detecte IN ('healthtech', 'fintech', 'aucun')",
            name='ck_project_sector_detection_secteur_detecte',
        ),
    )

    op.create_table(
        'healthtech_data_profile',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('est_dispositif_medical', sa.Boolean(), nullable=True),
        sa.Column('fournit_aide_decision_diagnostique_ou_therapeutique', sa.Boolean(), nullable=True),
        sa.Column('risque_deces_ou_deterioration_irreversible', sa.Boolean(), nullable=True),
        sa.Column('risque_intervention_chirurgicale_ou_deterioration_grave', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_healthtech_data_profile_project_id'),
    )

    op.create_table(
        'project_healthtech_classification',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('classe_risque', sa.Text(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_project_healthtech_classification_project_id'),
        sa.CheckConstraint(
            "classe_risque IN ('non_dispositif_medical', 'I', 'IIa', 'IIb', 'III')",
            name='ck_project_healthtech_classification_classe_risque',
        ),
    )

    op.create_table(
        'fintech_data_profile',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gere_fonds_ou_paiements_clients', sa.Boolean(), nullable=True),
        sa.Column('volume_mensuel_depasse_3_millions', sa.Boolean(), nullable=True),
        sa.Column('propose_transmission_de_fonds', sa.Boolean(), nullable=True),
        sa.Column('gere_investissement_ou_actifs', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_fintech_data_profile_project_id'),
    )

    op.create_table(
        'project_fintech_classification',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type_agrement', sa.Text(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', name='uq_project_fintech_classification_project_id'),
        sa.CheckConstraint(
            "type_agrement IN ('aucun', 'agrement_simplifie', 'agrement_classique')",
            name='ck_project_fintech_classification_type_agrement',
        ),
    )


def downgrade() -> None:
    op.drop_table('project_fintech_classification')
    op.drop_table('fintech_data_profile')
    op.drop_table('project_healthtech_classification')
    op.drop_table('healthtech_data_profile')
    op.drop_table('project_sector_detection')

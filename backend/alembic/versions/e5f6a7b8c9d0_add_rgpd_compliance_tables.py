"""add rgpd compliance tables (service 3.3.1 / 3.3.4)

Revision ID: e5f6a7b8c9d0
Revises: d3a9f21c6b48
Create Date: 2026-09-16 00:00:00.000000

Cree les 4 tables du service RGPD :
- compliance_data_profile : profil de traitement de donnees, 1 ligne/projet,
  capture a la premiere visite de la carte RGPD (pas a l'onboarding).
- project_rgpd_obligations : table "vivante" des obligations applicables,
  statut coche par l'entrepreneur (jamais ecrase par une regeneration, logique
  portee par le service).
- project_rgpd_obligations_history : archive figee (snapshot autonome, pas de
  FK vivante), alimentee uniquement lors d'une regeneration majeure.
- aipd_analyses : generateur one-shot declenche depuis la carte RGPD, lie de
  facon optionnelle a une obligation.

Voir les docstrings des modeles (backend/entrepreneur/models/) pour le detail
des decisions actees.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd3a9f21c6b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. compliance_data_profile
    op.create_table(
        'compliance_data_profile',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('collecte_donnees_sensibles', sa.Boolean(), nullable=True),
        sa.Column('collecte_donnees_mineurs', sa.Boolean(), nullable=True),
        sa.Column('profilage', sa.Boolean(), nullable=True),
        sa.Column('partage_avec_tiers', sa.Boolean(), nullable=True),
        sa.Column('transfert_hors_ue', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_compliance_data_profile_project_id'),
    )

    # 2. project_rgpd_obligations
    op.create_table(
        'project_rgpd_obligations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('statut', sa.String(20), server_default='a_faire', nullable=False),
        sa.Column('legal_text_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['legal_text_id'], ['legal_texts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'nom', name='uq_project_rgpd_obligations_project_nom'),
        sa.CheckConstraint("statut IN ('a_faire', 'fait')", name='ck_project_rgpd_obligations_statut'),
    )

    # 3. project_rgpd_obligations_history
    op.create_table(
        'project_rgpd_obligations_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("statut IN ('a_faire', 'fait')", name='ck_project_rgpd_obligations_history_statut'),
    )

    # 4. aipd_analyses
    op.create_table(
        'aipd_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_rgpd_obligation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('contenu', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_rgpd_obligation_id'], ['project_rgpd_obligations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('aipd_analyses')
    op.drop_table('project_rgpd_obligations_history')
    op.drop_table('project_rgpd_obligations')
    op.drop_table('compliance_data_profile')

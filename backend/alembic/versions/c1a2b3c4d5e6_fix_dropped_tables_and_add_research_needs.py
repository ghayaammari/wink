"""fix dropped gap_analysis tables + restore FK ondelete + create research_needs

La migration b9fa4c19666b (générée par autogenerate avec un metadata
incomplet -- `ProjectFintechGapAnalysis` et `ProjectHealthtechGapAnalysis`
n'étaient pas importés dans backend/entrepreneur/models/__init__.py) a par
erreur :
1. DROP les tables `project_fintech_gap_analysis` et
   `project_healthtech_gap_analysis` (au lieu de créer `research_needs`,
   son but réel).
2. Recréé la FK `project_legal_profiles.legal_representative_associate_id`
   sans `ondelete='SET NULL'` (le modèle project_legal_profile.py avait
   lui-même ce bug, corrigé en parallèle -- voir migration e1b2c3d4e5f6
   pour l'ondelete d'origine).
3. N'a jamais créé `research_needs`.

Cette migration corrective : recrée les 2 tables gap_analysis à l'identique
(vides -- aucune récupération de données possible, voir échange avec
l'utilisateur), restaure l'ondelete='SET NULL' de la FK, et crée enfin
`research_needs` (service 7.7.1).

Revision ID: c1a2b3c4d5e6
Revises: b9fa4c19666b
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b9fa4c19666b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- 1. Recréation des 2 tables supprimées par erreur (vides) ---
    op.create_table(
        'project_healthtech_gap_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chapitre', sa.Text(), nullable=False),
        sa.Column('obligations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "chapitre = ANY (ARRAY['obligations_fabricant'::text, 'evaluation_clinique'::text, 'surveillance_post_commercialisation'::text])",
            name='ck_project_healthtech_gap_analysis_chapitre',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='project_healthtech_gap_analysis_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='project_healthtech_gap_analysis_pkey'),
        sa.UniqueConstraint('project_id', 'chapitre', name='uq_project_healthtech_gap_analysis_project_chapitre'),
    )
    op.create_table(
        'project_fintech_gap_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('obligations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='project_fintech_gap_analysis_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='project_fintech_gap_analysis_pkey'),
        sa.UniqueConstraint('project_id', name='uq_project_fintech_gap_analysis_project_id'),
    )

    # --- 2. Restauration de l'ondelete='SET NULL' perdu ---
    op.drop_constraint(
        op.f('project_legal_profiles_legal_representative_associate_id_fkey'),
        'project_legal_profiles',
        type_='foreignkey',
    )
    op.create_foreign_key(
        op.f('project_legal_profiles_legal_representative_associate_id_fkey'),
        'project_legal_profiles',
        'project_associates',
        ['legal_representative_associate_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # --- 3. Création réelle de research_needs (but initial de b9fa4c19666b) ---
    op.create_table(
        'research_needs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type_besoin', sa.String(20), nullable=False),
        sa.Column('titre', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('statut', sa.String(20), server_default='ouvert', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("type_besoin IN ('probleme', 'expertise')", name='ck_research_needs_type_besoin'),
        sa.CheckConstraint("statut IN ('ouvert', 'ferme')", name='ck_research_needs_statut'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='research_needs_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='research_needs_pkey'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('research_needs')

    op.drop_constraint(
        op.f('project_legal_profiles_legal_representative_associate_id_fkey'),
        'project_legal_profiles',
        type_='foreignkey',
    )
    op.create_foreign_key(
        op.f('project_legal_profiles_legal_representative_associate_id_fkey'),
        'project_legal_profiles',
        'project_associates',
        ['legal_representative_associate_id'],
        ['id'],
    )

    op.drop_table('project_fintech_gap_analysis')
    op.drop_table('project_healthtech_gap_analysis')

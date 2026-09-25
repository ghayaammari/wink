"""add project_healthtech_gap_analysis table

Revision ID: j7e9f1a3b5c7
Revises: h5c7d9e1f3a5
Create Date: 2026-09-20 00:00:00.000000

Service 3.3.6 (diagnostic d'écart), volet HealthTech — voir
backend/entrepreneur/models/project_healthtech_gap_analysis.py pour le
raisonnement complet (pas de champ statut, 1 ligne par (projet, chapitre)).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'j7e9f1a3b5c7'
down_revision: Union[str, Sequence[str], None] = 'h5c7d9e1f3a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_healthtech_gap_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chapitre', sa.Text(), nullable=False),
        sa.Column('obligations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'chapitre', name='uq_project_healthtech_gap_analysis_project_chapitre'),
        sa.CheckConstraint(
            "chapitre IN ('obligations_fabricant', 'evaluation_clinique', 'surveillance_post_commercialisation')",
            name='ck_project_healthtech_gap_analysis_chapitre',
        ),
    )


def downgrade() -> None:
    op.drop_table('project_healthtech_gap_analysis')

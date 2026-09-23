"""add project_fintech_gap_analysis table

Revision ID: k8f0g2b4c6d8
Revises: j7e9f1a3b5c7
Create Date: 2026-09-20 00:00:00.000000

Service 3.3.6 (diagnostic d'écart), volet FinTech — 1 seule ligne par projet
(pas de chapitres, contrairement au volet HealthTech), voir
backend/entrepreneur/models/project_fintech_gap_analysis.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'k8f0g2b4c6d8'
down_revision: Union[str, Sequence[str], None] = 'j7e9f1a3b5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_fintech_gap_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('obligations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_project_fintech_gap_analysis_project_id'),
    )


def downgrade() -> None:
    op.drop_table('project_fintech_gap_analysis')

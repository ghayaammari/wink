"""add project_copilot_conversations table

Revision ID: m9a1b3c5d7e9
Revises: k8f0g2b4c6d8
Create Date: 2026-09-20 00:00:00.000000

Copilot conformite (agents/orchestrator/copilot_agent_service.py) -- passe
d'une conversation ephemere, non persistee (V1) a plusieurs conversations
nommees par projet, listees dans une barre laterale (comme l'historique de
Claude). Voir backend/entrepreneur/models/project_copilot_conversation.py
pour le choix de stocker `messages` en JSONB plutot qu'une table dediee.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'm9a1b3c5d7e9'
down_revision: Union[str, Sequence[str], None] = 'k8f0g2b4c6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_copilot_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('titre', sa.Text(), server_default='Nouvelle conversation', nullable=False),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('project_copilot_conversations')

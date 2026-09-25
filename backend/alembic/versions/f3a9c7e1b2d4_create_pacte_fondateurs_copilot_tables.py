"""create pacte_fondateurs copilot tables (agent_pacte_fondateur)

Service 1.1.13 (pacte de fondateurs), agent conversationnel (categorie 3).

ISOLATION VOLONTAIRE (decision actee avec l'utilisateur, 22/09/2026) : la
binome travaille en parallele sur un agent copilot (Groupe 3 -- roadmap,
schema officiel copilot_conversations/copilot_messages/copilot_responses/
copilot_response_sources dans "Wink -- Schemas Increment 1 v3"), code pas
encore pushe. Pour eviter toute collision au moment du pull (meme nom de
table = conflit garanti, independamment du dossier Python), ces 4 tables
sont prefixees pacte_fondateurs_* -- un espace de noms SQL dedie, distinct
du schema officiel. Consequence assumee : le jour de la fusion avec le code
de la binome, ce sera une vraie migration de donnees (mapper ces tables vers
les tables officielles), pas un simple merge git -- decision actee, pas une
inadvertance.

Simplification par rapport au schema officiel : pas de colonne `nom` sur la
conversation -- un seul fil persistant par projet (la "bulle" toujours
accessible), pas plusieurs conversations nommees. UniqueConstraint sur
project_id pour le garantir. A reconsiderer si un jour plusieurs fils
paralleles sont demandes.

Ajout absent du schema officiel : `code_clause_contexte` (nullable) sur
pacte_fondateurs_messages -- capture la clause affichee au moment de la
question (contexte de page), necessaire pour le besoin "expliquer cette
clause" (voir discussion architecture, 22/09/2026). Le schema officiel
(question TEXT seul) ne portait pas cette info.

Revision ID: f3a9c7e1b2d4
Revises: 6a1e9c2f4b7d
Create Date: 2026-09-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a9c7e1b2d4'
down_revision: Union[str, Sequence[str], None] = '6a1e9c2f4b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE (pre-existant, pas cause par cette migration) : le repo a deja 3 heads
# Alembic divergents au moment ou cette migration est ecrite (6a1e9c2f4b7d,
# 82a64157b35d, a1b2c3d4e5f6) -- `alembic upgrade head` echouera avec
# "Multiple head revisions" tant qu'un `alembic merge heads` n'est pas fait.
# Cette migration chaine sur 6a1e9c2f4b7d (la plus proche thematiquement,
# document_generation) mais ne resout pas la divergence des 2 autres heads --
# hors perimetre de ce travail, signale pour eviter la surprise.


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pacte_fondateurs_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            ondelete='CASCADE', name='fk_pacte_fondateurs_conversations_project_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_pacte_fondateurs_conversations_project_id'),
    )

    op.create_table(
        'pacte_fondateurs_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('code_clause_contexte', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['conversation_id'], ['pacte_fondateurs_conversations.id'],
            ondelete='CASCADE', name='fk_pacte_fondateurs_messages_conversation_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'pacte_fondateurs_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reponse', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['message_id'], ['pacte_fondateurs_messages.id'],
            ondelete='CASCADE', name='fk_pacte_fondateurs_responses_message_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', name='uq_pacte_fondateurs_responses_message_id'),
    )

    op.create_table(
        'pacte_fondateurs_response_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('response_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['response_id'], ['pacte_fondateurs_responses.id'],
            ondelete='CASCADE', name='fk_pacte_fondateurs_response_sources_response_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('pacte_fondateurs_response_sources')
    op.drop_table('pacte_fondateurs_responses')
    op.drop_table('pacte_fondateurs_messages')
    op.drop_table('pacte_fondateurs_conversations')

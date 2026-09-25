"""create document_generation_variable_values

Service 1.1.13 (pacte de fondateurs v2). Décision actée avec l'utilisateur
(21/09/2026) : aujourd'hui les valeurs saisies pour un document généré ne
survivent qu'en JSONB dans `document_generation_sessions.reponses`, jamais
sous forme structurée une fois le document finalisé -- impossible de
consulter/modifier une variable précise d'un pacte déjà signé sans rejouer
toute la session. Cette table capture un instantané figé de chaque variable
injectée, au moment de la finalisation seulement (jamais pendant la session
en cours -- une seule source de vérité pendant la rédaction : `reponses`).

Clé vers `document_versions.id` (pas `documents.id`) : une future re-finalisation
(nouvelle version du même document) doit pouvoir garder l'instantané de
l'ancienne version intact, pas l'écraser.

Revision ID: 6a1e9c2f4b7d
Revises: 507ed2995d84
Create Date: 2026-09-21 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6a1e9c2f4b7d'
down_revision: Union[str, Sequence[str], None] = '507ed2995d84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_generation_variable_values',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code_section', sa.String(length=255), nullable=False),
        sa.Column('code_clause', sa.String(length=80), nullable=True),
        sa.Column('nom_variable', sa.String(length=120), nullable=False),
        sa.Column('type_variable', sa.String(length=30), nullable=False),
        sa.Column('valeur', sa.Text(), nullable=True),
        sa.Column('saisie_manuellement', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_version_id'], ['document_versions.id'],
            ondelete='CASCADE', name='fk_document_generation_variable_values_document_version_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'document_version_id', 'code_section', 'nom_variable',
            name='uq_document_generation_variable_values_version_section_variable',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('document_generation_variable_values')

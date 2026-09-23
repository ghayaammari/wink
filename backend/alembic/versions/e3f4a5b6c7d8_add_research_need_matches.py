"""add research_need_matches (service 7.7.2, matching_agent chercheur)

Table du résultat persisté du matching_agent pour un besoin scientifique
(research_needs) -- voir backend/matching/models/research_need_match.py.

NOTE MULTI-HEADS : au 22/09/2026, `alembic/versions/` contient plusieurs
têtes non fusionnées (au moins f1a2b3c4d5e6 et m9a1b3c5d7e9, en plus de
celle-ci) -- pas lié à ce chantier, pré-existant. Cette migration chaîne
sur d2e3f4a5b6c7 (dernière tête confirmée appliquée avec succès en session
le 22/09/2026). Si `alembic upgrade head` échoue avec "Multiple head
revisions are present", lancer `alembic merge heads` avant de réessayer --
ne pas improviser un merge à la main dans ce fichier.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'research_need_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('research_need_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('matches', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('synthese', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['research_need_id'], ['research_needs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('research_need_id', name='uq_research_need_matches_research_need_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('research_need_matches')

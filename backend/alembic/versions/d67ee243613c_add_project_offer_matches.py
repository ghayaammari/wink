"""add project_offer_matches (EPIC-06, matching startup -> offres)

Volet Startup -> Offres du matching (sens inverse de investment_offer_
matches) -- voir backend/entrepreneur/models/project_offer_match.py.

Revision ID: d67ee243613c
Revises: 364b5606ee42
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd67ee243613c'
down_revision: Union[str, Sequence[str], None] = '364b5606ee42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'project_offer_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('matches', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('synthese', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_project_offer_matches_project_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('project_offer_matches')

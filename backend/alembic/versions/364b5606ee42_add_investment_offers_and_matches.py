"""add investment_offers and investment_offer_matches (EPIC-07, matching investisseur)

Volet Investisseur -> Startup du matching (miroir de research_needs /
research_need_matches, sens inverse) -- voir backend/investisseur/models/
investment_offer.py et investment_offer_match.py.

Revision ID: 364b5606ee42
Revises: b7c8d9e0f1a2
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '364b5606ee42'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'investment_offers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('investor_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('titre', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('montant_propose', sa.Integer(), nullable=False),
        sa.Column('secteurs_cibles', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('stades_cibles', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('statut', sa.String(length=20), server_default='ouvert', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['investor_profile_id'], ['investor_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('montant_propose > 0', name='ck_investment_offers_montant_propose_positif'),
        sa.CheckConstraint("statut IN ('ouvert', 'ferme')", name='ck_investment_offers_statut'),
    )
    op.create_table(
        'investment_offer_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('investment_offer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('matches', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('synthese', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['investment_offer_id'], ['investment_offers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('investment_offer_id', name='uq_investment_offer_matches_offer_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('investment_offer_matches')
    op.drop_table('investment_offers')

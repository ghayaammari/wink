"""add project_pitch_profiles et project_pitch_decks

Revision ID: n1b3c5d7e9f1
Revises: m9a1b3c5d7e9
Create Date: 2026-09-21 00:00:00.000000

Service 6.6.2 (generateur de pitch deck) — voir
backend/entrepreneur/models/project_pitch_profile.py et
project_pitch_deck.py pour le detail des deux tables et le raisonnement
(pourquoi separees, pourquoi pas de versioning).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "n1b3c5d7e9f1"
down_revision: Union[str, Sequence[str], None] = "m9a1b3c5d7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_pitch_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("probleme", sa.Text(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("marche", sa.Text(), nullable=True),
        sa.Column("modele_economique", sa.Text(), nullable=True),
        sa.Column("concurrence", sa.Text(), nullable=True),
        sa.Column("traction", sa.Text(), nullable=True),
        sa.Column("financements", sa.Text(), nullable=True),
        sa.Column("roadmap", sa.Text(), nullable=True),
        sa.Column("demande_investissement", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )

    op.create_table(
        "project_pitch_decks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )


def downgrade() -> None:
    op.drop_table("project_pitch_decks")
    op.drop_table("project_pitch_profiles")

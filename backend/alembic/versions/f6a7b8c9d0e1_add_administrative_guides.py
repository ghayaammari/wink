"""add administrative_guides table

Revision ID: f6a7b8c9d0e1
Revises: e3f4a5b6c7d8
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Table generique de staging pour les guides web non-legaux de
    l'Increment 1 (pacte_fondateurs, pre_depot) — voir
    backend/shared/knowledge_base/models/administrative_guides.py.
    `content_embeddings.domaine` accepte deja ces 2 valeurs depuis la
    migration 6f1a2c9d3e5b, aucune modification necessaire de ce cote."""
    op.create_table(
        'administrative_guides',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('domaine', sa.String(length=50), nullable=False),
        sa.Column('source_nom', sa.String(length=150), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('titre', sa.String(length=255), nullable=True),
        sa.Column('texte_brut', sa.Text(), nullable=False),
        sa.Column('chunking_suggere', sa.String(length=20), server_default='par_paragraphe', nullable=False),
        sa.Column('statut_contenu', sa.String(length=20), server_default='extrait_automatique', nullable=False),
        sa.Column('collecte_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domaine', 'source_url', name='uq_administrative_guides_domaine_url'),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name='ck_administrative_guides_statut_contenu',
        ),
        sa.CheckConstraint(
            "domaine IN ('pacte_fondateurs', 'pre_depot')",
            name='ck_administrative_guides_domaine',
        ),
    )


def downgrade() -> None:
    op.drop_table('administrative_guides')

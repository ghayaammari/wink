"""add necessite_absence_investisseurs to document_templates

Service 1.1.13 (pacte de fondateurs) — préparation du Préambule scindé en
2 variantes ("avec investisseurs" / "fondateurs seuls", décision utilisateur
du 21/09/2026 : le texte du Préambule mentionne explicitement les Associés
Investisseurs, incohérent tel quel si le projet n'en a aucun).

`necessite_investisseurs` (migration d3a7c5e8f1b4) sait déjà sauter une
section si le projet N'A AUCUN investisseur -- il manquait le sens inverse :
sauter une section si le projet EN A AU MOINS UN. Sans ça, la variante
"fondateurs seuls" resterait affichée même quand des investisseurs existent
(les deux variantes visibles en même temps, incohérent). Colonne symétrique,
même mécanisme que `necessite_investisseurs`, pas un nouveau système de
règles.

Revision ID: c3d5e7f9a1b3
Revises: b2c4d6e8f0a2
Create Date: 2026-09-21 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d5e7f9a1b3'
down_revision: Union[str, Sequence[str], None] = 'b2c4d6e8f0a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_templates',
        sa.Column('necessite_absence_investisseurs', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'necessite_absence_investisseurs')

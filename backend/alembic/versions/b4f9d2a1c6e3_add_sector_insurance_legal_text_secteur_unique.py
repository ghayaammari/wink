"""add unique constraint (legal_text_id, secteur) on sector_insurance_recommendations

Revision ID: b4f9d2a1c6e3
Revises: a7b3c8d1e4f2
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4f9d2a1c6e3'
down_revision: Union[str, Sequence[str], None] = 'a7b3c8d1e4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Correctif du 11/09/2026 (voir plan de correction, service 1.1.10) :
    # garantit au niveau DB qu'un article legal_texts ne peut plus jamais en
    # écraser un autre pour un même secteur dans sector_insurance_recommendations.
    # NULL != NULL en SQL, donc cette contrainte ne s'applique qu'aux lignes
    # du volet base légale (legal_text_id non nul).
    op.create_unique_constraint(
        'uq_sector_insurance_legal_text_secteur',
        'sector_insurance_recommendations',
        ['legal_text_id', 'secteur'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_sector_insurance_legal_text_secteur',
        'sector_insurance_recommendations',
        type_='unique',
    )

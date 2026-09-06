"""add check constraint on funding_visibility/compliance_visibility

Revision ID: 82a64157b35d
Revises: 762facc83856
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82a64157b35d'
down_revision: Union[str, Sequence[str], None] = '762facc83856'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Aucune valeur autre que le défaut 'private' n'a jamais pu être écrite jusqu'ici
    # (aucun chemin applicatif n'existait pour ces 2 colonnes) — pas de données à
    # corriger avant d'ajouter la contrainte.
    op.create_check_constraint(
        'ck_project_public_profiles_funding_visibility',
        'project_public_profiles',
        "funding_visibility IN ('private', 'public', 'investors_only')",
    )
    op.create_check_constraint(
        'ck_project_public_profiles_compliance_visibility',
        'project_public_profiles',
        "compliance_visibility IN ('private', 'public', 'investors_only')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_project_public_profiles_compliance_visibility', 'project_public_profiles', type_='check'
    )
    op.drop_constraint(
        'ck_project_public_profiles_funding_visibility', 'project_public_profiles', type_='check'
    )

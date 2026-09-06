"""fix investor_profiles_completion check constraint (double %% bug) + add investor_type

Revision ID: a1b2c3d4e5f6
Revises: 450f7ec8f344
Create Date: 2026-09-06 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '450f7ec8f344'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deux corrections en une seule migration (base de dev perso, pas
    encore partagée — pas besoin de deux révisions séparées) :
    1) La migration précédente (450f7ec8f344) a généré '0%%' au lieu de '0%'
       dans la CHECK constraint de profile_completion — bug d'échappement
       psycopg2/pyformat, alors que ce projet utilise psycopg (v3).
    2) Ajout de investor_type (obligatoire à l'onboarding, colonne nullable
       en base) — compte désormais dans profile_completion, qui passe de 3
       à 4 paliers (0/33/67/100%, un par champ rempli sur investor_type,
       investment_thesis, contact_email)."""
    op.drop_constraint('ck_investor_profiles_completion', 'investor_profiles', type_='check')

    op.add_column('investor_profiles', sa.Column('investor_type', sa.String(length=30), nullable=True))
    op.create_check_constraint(
        'ck_investor_profiles_investor_type',
        'investor_profiles',
        "investor_type IN ('vc', 'business_angel', 'family_office', 'corporate_vc', 'fonds_public', 'autre')",
    )

    op.create_check_constraint(
        'ck_investor_profiles_completion',
        'investor_profiles',
        "profile_completion IN ('0%', '33%', '67%', '100%')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_investor_profiles_completion', 'investor_profiles', type_='check')
    op.drop_constraint('ck_investor_profiles_investor_type', 'investor_profiles', type_='check')
    op.drop_column('investor_profiles', 'investor_type')
    op.create_check_constraint(
        'ck_investor_profiles_completion',
        'investor_profiles',
        "profile_completion IN ('0%%', '50%%', '100%%')",
    )
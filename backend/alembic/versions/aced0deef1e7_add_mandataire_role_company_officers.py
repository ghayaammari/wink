"""add 'mandataire' to company_officers.role CHECK constraint

Service 1.1.4 (statuts SAS) — art. 44 (mandat_actes_societe_en_formation) et
l'Annexe III de clôture désignent un mandataire chargé des actes pour le
compte de la société en formation. Ce mandat n'était pas couvert par le CHECK
initial (`president`|`directeur_general`|`membre_comite`), pensé uniquement
pour les art. 39-41.

Même table, même logique anti-redondance (`associate_id` nullable) : le
mandataire est très souvent l'un des fondateurs déjà présent dans
`project_associates`, mais rien ne l'empêche d'être un tiers (ex. un
professionnel du droit mandaté) — d'où le choix de l'ajouter ici plutôt que
de créer un mécanisme séparé.

Revision ID: aced0deef1e7
Revises: e4f6a8b2c0d1
Create Date: 2026-09-23 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'aced0deef1e7'
down_revision: Union[str, Sequence[str], None] = 'e4f6a8b2c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('ck_company_officers_role', 'company_officers', type_='check')
    op.create_check_constraint(
        'ck_company_officers_role',
        'company_officers',
        "role IN ('president', 'directeur_general', 'membre_comite', 'mandataire')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_company_officers_role', 'company_officers', type_='check')
    op.create_check_constraint(
        'ck_company_officers_role',
        'company_officers',
        "role IN ('president', 'directeur_general', 'membre_comite')",
    )

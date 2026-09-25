"""add capital data (capital, lieu d'immatriculation, actions) to project_legal_profiles

Service 1.1.13 (pacte de fondateurs) -- passe de classification des variables
(21/09/2026) : sur les 202 variables des 10 articles + Préambule, 4 sont des
faits fixes du projet qui n'existaient encore nulle part en base --
`capital_social`, `lieu_immatriculation`, `nombre_actions`, `valeur_nominale`.
Utilisées pour l'instant uniquement par le Préambule du pacte
(`preambule_avec_investisseurs`/`preambule_sans_investisseurs`,
`decisions_articles.json`), saisies aujourd'hui à la main -- deviendront des
variables `auto_*` (résolution automatique, comme `auto_nom_societe`) dans
une passe ultérieure côté `document_generation_service.py`, hors scope de
cette migration (schéma seulement).

Point de vigilance signalé (pas un bug, une clarification de nommage) :
`project_associates` porte déjà des colonnes `capital_social` et
`lieu_immatriculation` (migration b2c4d6e8f0a2) -- mais pour une raison
différente : ce sont les infos d'un ASSOCIÉ qui est lui-même une personne
morale (ex. un fonds d'investissement), pas celles du projet/de la société
dont ce pacte parle. Même nom de colonne, table différente, sémantique
différente -- pas une duplication, juste à garder en tête en code review.

`nombre_actions` n'est PAS dérivable de `project_associates.pourcentage_capital`
(un pourcentage, pas un nombre absolu de titres) -- vérifié avant d'ajouter
cette colonne, vraie donnée manquante.

Revision ID: 507ed2995d84
Revises: c3d5e7f9a1b3
Create Date: 2026-09-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '507ed2995d84'
down_revision: Union[str, Sequence[str], None] = 'c3d5e7f9a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project_legal_profiles', sa.Column('capital_social', sa.Numeric(14, 2), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('lieu_immatriculation', sa.String(120), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('nombre_actions', sa.Integer(), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('valeur_nominale', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_legal_profiles', 'valeur_nominale')
    op.drop_column('project_legal_profiles', 'nombre_actions')
    op.drop_column('project_legal_profiles', 'lieu_immatriculation')
    op.drop_column('project_legal_profiles', 'capital_social')

"""add project_associates.situation_et_regime_matrimonial

Service 1.1.4 (statuts SAS) — l'en-tête du clausier Bpifrance modélise le
patron personne physique des fondateurs avec l'état civil complet : prénom,
nom, adresse, date et lieu de naissance, et situation matriciale
(`situation_et_regime_matrimonial`, ex. "marié(e) sous le régime de la
communauté légale"). Tous les autres champs existaient déjà sur
`project_associates` ; celui-ci manquait (vérifié dans le modèle et les
schémas le 22/09/2026).

Décision de conception (actée avec l'utilisateur, 22/09/2026) : attribut
durable de l'associé personne physique, pas une variable de session de
génération — c'est un fait d'état civil réutilisable (statuts, puis
éventuellement DBE 1.1.6), comme `date_naissance` / `lieu_naissance`. Saisie
libre (texte) plutôt qu'un enum : les régimes matrimoniaux ne forment pas une
liste fermée. NULLABLE : renseigné au moment de la génération, sans CHECK
inter-champs (exigible seulement si type_personne='personne_physique',
cohérent avec le reste de la table).
(réalisé par OPENCODE)

Revision ID: d6b8a4f2e0c9
Revises: f3a9c7e1b2d4
Create Date: 2026-09-22 17:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd6b8a4f2e0c9'
down_revision: Union[str, Sequence[str], None] = 'f3a9c7e1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'project_associates',
        sa.Column('situation_et_regime_matrimonial', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_associates', 'situation_et_regime_matrimonial')
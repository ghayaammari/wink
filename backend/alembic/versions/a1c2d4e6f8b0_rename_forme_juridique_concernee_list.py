"""rename document_templates.forme_juridique_concernee to formes_juridiques_concernees (list)

Service 1.1.13 (pacte de fondateurs), cases 95-96 (rôle du Mandataire, para
478) — première utilisation réelle de `forme_juridique_concernee` avec des
données de seed (toutes les sections existantes l'avaient à `null` jusqu'ici).
Le texte Bpifrance oppose "société par action" à "SARL" : "société par
action" désigne une FAMILLE de formes juridiques (SAS, SASU, SA), pas une
seule — or `forme_juridique_concernee` (String) ne pouvait comparer qu'à UNE
valeur exacte (`section.forme_juridique_concernee != forme_juridique` dans
`_applicable()`), et ne pouvait donc pas exprimer cette famille.

Décision (actée avec l'utilisateur, 20/09/2026) : remplacer directement la
colonne par une liste JSONB plutôt que d'ajouter un mécanisme séparé pour ce
seul cas — corrige le mécanisme au niveau qui en a besoin (pas seulement ce
cas précis) et sert au futur 1.1.4 (statuts), qui aura le même besoin
(clause valable pour "SAS+SASU" mais pas "SARL", par ex.). Remplacement direct
sans migration de données : la colonne n'a encore jamais été renseignée en
seed, aucune ligne existante à convertir.

Limite assumée, signalée mais volontairement pas corrigée ici (hors périmètre
1.1.13) : `project_legal_profiles.legal_form` reste un texte libre sans
liste fermée de valeurs (pas de `CHECK` en base) — une valeur mal
orthographiée ("S.A.S" au lieu de "SAS") ne matchera toujours aucune entrée
de `formes_juridiques_concernees`. Normaliser `legal_form` est un sujet de
1.1.1/1.1.4, pas de ce service.

Revision ID: a1c2d4e6f8b0
Revises: f6b3e9a2c5d7
Create Date: 2026-09-20 19:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'a1c2d4e6f8b0'
down_revision: Union[str, Sequence[str], None] = 'f6b3e9a2c5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('document_templates', 'forme_juridique_concernee')
    op.add_column(
        'document_templates',
        sa.Column('formes_juridiques_concernees', JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'formes_juridiques_concernees')
    op.add_column(
        'document_templates',
        sa.Column('forme_juridique_concernee', sa.String(length=60), nullable=True),
    )

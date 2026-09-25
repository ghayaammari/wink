"""add nom_complet (personne physique dirigeante) to company_officers

Service 1.1.4 (statuts SAS) — art. 39-41 (Président/Directeur Général/membres
du Comité de Direction) et art. 44/clôture (mandataire).

Trou trouvé en câblant le moteur de génération (23/09/2026) : `company_officers`
ne portait des champs d'identité complets que pour un dirigeant PERSONNE
MORALE non associé (`denomination_sociale`, `representant_nom`/`representant_prenom`,
...). Un dirigeant PERSONNE PHYSIQUE non associé (l'exemple même qui justifie
la table dans sa docstring — "Charlotte, présidente sans capital ni
type_apport") n'avait nulle part où stocker son NOM : le modèle initial
supposait à tort qu'un dirigeant personne physique est toujours un associé
(`associate_id` obligatoire dans ce cas), ce qui contredit son propre exemple
motivant.

`adresse` existe déjà sur cette table (colonne générique, pas réservée à la
personne morale) — réutilisée telle quelle pour ce cas, pas dupliquée. Seul
`nom_complet` manquait.

`nom_complet` : même nom et même sémantique que sur `project_associates`
(personne physique associée) — même convention "même nom, table différente,
ne pas confondre en code review" déjà utilisée pour les champs personne
morale de cette table. Utilisé seulement si `type_personne='personne_physique'`
ET `associate_id IS NULL` — sinon l'identité vit dans `project_associates`
(anti-redondance inchangée).

NULLABLE, pas de CHECK inter-champs : cohérent avec le reste de la table.

Revision ID: acb040c7128a
Revises: aced0deef1e7
Create Date: 2026-09-23 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'acb040c7128a'
down_revision: Union[str, Sequence[str], None] = 'aced0deef1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('company_officers', sa.Column('nom_complet', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('company_officers', 'nom_complet')

"""add description_apport_nature to project_associates

Service 1.1.4 (statuts SAS) — audit du clausier du 23/09/2026, correction #4
(ex-P2).

Contexte : `designation_bien_apporte` (ce qu'un associé apporte en nature —
un bien, pas de l'argent) ne vivait jusqu'ici que dans la session du document
statuts (`session.reponses["apport_nature_identite"]`), invisible à tout
autre service Wink qui voudrait un jour savoir "qu'a apporté cet associé"
(ex. un récapitulatif des apports ailleurs dans l'app). Décision produit
(23/09/2026) : en faire un attribut persistant de l'associé plutôt qu'une
donnée piégée dans un document.

`description_apport_nature` : NULLABLE, pertinente seulement si
`type_apport='nature'` — pas de CHECK inter-champs, cohérent avec le reste
de la table (même convention que les champs personne morale déjà nullable
sans contrainte croisée).

Le résolveur (`statuts_sas_resolvers.py`,
`_valeurs_apports_nature_par_associe`) doit être étendu pour lire cette
colonne en priorité, et le point de soumission de la clause
`apport_nature_identite` doit écrire dedans (voir note dans le résolveur —
écriture pas encore câblée, à faire dans `document_generation_service.py`).

Revision ID: d3f7a1c9e5b4
Revises: acb040c7128a
Create Date: 2026-09-23 23:55:00.000000

NOTE (24/09/2026) : `acb040c7128a_add_identite_pp_company_officers.py`
(ajout de `company_officers.nom_complet`) existait dans un espace de travail
d'une session antérieure mais n'avait jamais été copiée dans ce dépôt --
écart trouvé et corrigé en même temps que cette migration (le modèle
`company_officer.py` référence déjà cette colonne, la migration manquait).
Chaîne réelle de ce projet : ... -> aced0deef1e7 -> acb040c7128a -> d3f7a1c9e5b4.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3f7a1c9e5b4'
down_revision: Union[str, Sequence[str], None] = 'acb040c7128a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project_associates', sa.Column('description_apport_nature', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_associates', 'description_apport_nature')

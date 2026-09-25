"""add project_associates.est_fondateur

Service 1.1.13 (pacte de fondateurs) — Phase 1b (extraction des variables du
template Bpifrance) a mis en évidence que le pacte distingue explicitement
"Associés Fondateurs" et "Associés Investisseurs" dans son préambule, une
distinction qu'aucune colonne de `project_associates` ne portait jusqu'ici
(seul `est_partie_au_pacte_fondateurs` existait, qui dit SI un associé est
partie au pacte, pas DE QUEL CÔTÉ).

Décision de conception (actée avec l'utilisateur, 20/09/2026) : ajouter cette
distinction comme attribut durable de l'associé plutôt que de la redemander à
chaque document généré (option écartée : la stocker uniquement dans
`document_generation_sessions.reponses`, propre à 1.1.13). Justification :
c'est un fait sur le rôle de la personne dans l'entreprise, pas un détail du
document — 1.1.4 (statuts) réutilise le même moteur de génération
(document_generation_service.py, générique par `document_type`) et aura
vraisemblablement besoin de la même information.

Nommage : `est_fondateur` (booléen indépendant, même famille que
`est_dirigeant` / `est_partie_au_pacte_fondateurs`), volontairement PAS
`est_investisseur` — `users.role` porte déjà une valeur `'investisseur'` pour
le rôle de connexion à la plateforme Wink, un nom identique sur
`project_associates` aurait entretenu la confusion entre "rôle compte Wink"
et "rôle dans le pacte de CETTE entreprise". Booléen plutôt qu'un enum
fondateur/investisseur à 2 valeurs : un associé peut n'être ni l'un ni
l'autre (ex. un proche investisseur non partie au pacte) — un enum binaire
aurait forcé un classement inexact.
(réalisé par OPENCODE)

Revision ID: c8f4d1a6b2e9
Revises: b7e2f4a9c1d6
Create Date: 2026-09-20 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f4d1a6b2e9'
down_revision: Union[str, Sequence[str], None] = 'b7e2f4a9c1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'project_associates',
        sa.Column('est_fondateur', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_associates', 'est_fondateur')

"""add document_templates.necessite_investisseurs

Service 1.1.13 (pacte de fondateurs) — point soulevé par l'utilisateur en
relisant les cas `A_CONFIRMER` de l'extraction Phase 1b : si le projet n'a
aucun associé Investisseur (répartition 100 % Fondateurs), les sections du
pacte qui ne concernent QUE les Associés Investisseurs (droits qui leur sont
propres, ex. sortie conjointe réservée aux Investisseurs) ne doivent pas être
posées à l'utilisateur — les lui montrer produirait un questionnaire
incohérent avec son projet réel.

Le mécanisme de saut de section existe déjà (`_applicable()` dans
document_generation_service.py), mais ne teste aujourd'hui que la forme
juridique (`document_templates.forme_juridique_concernee`, ajoutée pour 1.1.4
/statuts). Cette migration étend le même mécanisme avec un 2e critère
indépendant, plutôt que de créer un système de règles séparé — un service qui
consulte deux mécanismes différents pour la même question ("cette section
s'applique-t-elle ?") serait plus difficile à maintenir qu'un seul point
d'entrée avec plusieurs conditions.

Détection "le projet a des investisseurs" : au moins une ligne
`project_associates` avec `est_partie_au_pacte_fondateurs=true` ET
`est_fondateur=false` (colonne ajoutée par la migration précédente,
c8f4d1a6b2e9) — voir document_generation_service._advance_to_next_section.
(réalisé par OPENCODE)

Revision ID: d3a7c5e8f1b4
Revises: c8f4d1a6b2e9
Create Date: 2026-09-20 13:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3a7c5e8f1b4'
down_revision: Union[str, Sequence[str], None] = 'c8f4d1a6b2e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_templates',
        sa.Column('necessite_investisseurs', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'necessite_investisseurs')

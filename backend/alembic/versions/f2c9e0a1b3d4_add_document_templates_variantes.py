"""add document_templates.variantes_candidates + variante_obligatoire type_contenu

Service 1.1.13 (Pacte de fondateurs interactif). Corrige une décision prise dans
e4a8f1c9b2d7 avant que les données réelles du template Bpifrance soient
disponibles : cette migration proposait de résoudre un groupe de clauses
mutuellement exclusives (ex. Article 3, 7 hypothèses de préemption/préférence)
par un préfixe commun de `contract_clauses_library.scenario`. Une fois les 44
scénarios réels extraits, ce préfixe ne tient pas (ex. `sortie_conjointe_*` et
`sortie_forcee_*` partagent un préfixe thématique "sortie" sans être le même
groupe de variantes ; `limitation_participations` appartient au groupe
"inalienabilite" sans en partager le préfixe). Remplacé par une liste explicite
de scenarios candidats portée directement par la section de squelette
(`document_templates.variantes_candidates`), voir docstring du modèle
DocumentTemplate.

Nouvelle migration plutôt qu'une édition de e4a8f1c9b2d7, dont l'état "déjà
appliquée ou non" côté utilisateur n'est pas confirmé au moment où ce correctif
est écrit — éditer une migration potentiellement déjà jouée casserait
l'historique Alembic chez qui l'a déjà appliquée.

Revision ID: f2c9e0a1b3d4
Revises: e4a8f1c9b2d7
Create Date: 2026-09-20 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f2c9e0a1b3d4'
down_revision: Union[str, Sequence[str], None] = 'e4a8f1c9b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Le CHECK sur type_contenu inclut déjà 'variante_obligatoire' depuis
    e4a8f1c9b2d7 — seule la colonne manque ici.
    """
    op.add_column(
        'document_templates',
        sa.Column('variantes_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'variantes_candidates')

"""add contract_clauses_library.sous_variantes_candidates

Service 1.1.13 (Pacte de fondateurs interactif). La ré-extraction du modèle
Bpifrance (segmentation structurelle du 20/09/2026, voir
`extract_pacte_fondateurs_raw.py` / `segment_pacte_fondateurs_articles.py`) a
révélé qu'un seul article (Article 3, 3 de ses 7 hypothèses de préemption/
préférence) contient un second niveau de choix imbriqué dans le premier :
après avoir choisi une hypothèse de rang, l'utilisateur doit encore choisir
entre "droit de préemption portant sur la totalité des Titres uniquement" et
"faculté d'exercice partiel" — deux mécanismes juridiques différents, pas une
simple variable à remplir. Vérifié structurellement : ce cas n'existe nulle
part ailleurs dans les 10 articles du modèle.

Plutôt que d'ajouter un second niveau à `document_templates.variantes_candidates`
(qui resterait à plat pour les 9 autres sections `variante_obligatoire` du
service, sans besoin), le second niveau est porté directement par la clause
candidate concernée — voir docstring du modèle `ContractClauseLibrary`.

Revision ID: b7e2f4a9c1d6
Revises: d9c4a6b1f3e8
Create Date: 2026-09-20 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e2f4a9c1d6'
down_revision: Union[str, Sequence[str], None] = 'd9c4a6b1f3e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'contract_clauses_library',
        sa.Column('sous_variantes_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contract_clauses_library', 'sous_variantes_candidates')

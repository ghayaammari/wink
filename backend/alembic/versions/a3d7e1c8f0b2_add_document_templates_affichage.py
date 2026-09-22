"""add document_templates.titre_affiche + explication (copilot display metadata)

Service 1.1.13 (Pacte de fondateurs interactif), frontend. Le scénario
fonctionnel exige, avant CHAQUE section (obligatoire, facultative, ou groupe
de variantes), une "explication courte : à quoi sert cette section" — et un
titre à annoncer. Pour les sections adossées à UNE clause (mention_obligatoire/
clause_optionnelle), `contract_clauses_library.titre_clause` et
`.scenario_description` suffisent déjà. Mais 6 sections n'ont pas cette
ressource : `identification_des_parties` (donnee_projet, aucune clause) et les
5 groupes `variante_obligatoire` (inalienabilite, preemption_preference,
sortie_conjointe, sortie_forcee, retrait) — un groupe n'a pas de titre/
description propre, seulement celles de chaque clause candidate.

Choix : stocker ce texte dans `document_templates` (nullable, rempli
seulement pour ces 6 lignes) plutôt que de le coder en dur côté frontend.
Raison : 1.1.4 (statuts) réutilisera le même moteur de session avec son propre
squelette de sections — dupliquer ces libellés dans le frontend les ferait
diverger silencieusement du squelette réel dès qu'il change. Rester dans
`document_templates` garde une seule source de vérité par `document_type`.

Revision ID: a3d7e1c8f0b2
Revises: f2c9e0a1b3d4
Create Date: 2026-09-20 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3d7e1c8f0b2'
down_revision: Union[str, Sequence[str], None] = 'f2c9e0a1b3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_templates', sa.Column('titre_affiche', sa.String(255), nullable=True))
    op.add_column('document_templates', sa.Column('explication', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'explication')
    op.drop_column('document_templates', 'titre_affiche')

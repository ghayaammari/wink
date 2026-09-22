"""add personne_morale fields to project_associates

Service 1.1.13 (pacte de fondateurs), traitement de l'entête du modèle
Bpifrance ("Entre les soussignés... (dénomination sociale)... représentée
par... en sa qualité de...") -- manque trouvé en essayant de reproduire ce
bloc : `project_associates` a bien `type_personne` ('personne_physique' /
'personne_morale'), mais AUCUN champ pour les informations propres à une
personne morale associée (une société elle-même associée du projet, ex. un
fonds d'investissement) -- seuls des champs pensés pour une personne physique
existent (date_naissance, lieu_naissance, nationalite).

8 champs ajoutés (dont 1 ajouté après relecture de "entete" -- voir plus
bas), tous NULLABLE (utilisés seulement si type_personne='personne_morale',
jamais pour une personne physique -- pas de CHECK inter-champs ajouté ici
pour rester cohérent avec le reste de la table, qui n'en impose pas non plus
entre type_personne et les champs personne physique existants) :
  - denomination_sociale, type_societe, capital_social, siege_social,
    lieu_immatriculation, numero_siren : identité de la société associée
    ("type_societe" ex. "SAS" -- ajouté après coup, oublié dans la première
    passe sur "entete", même nature que les autres, pas une nouvelle
    décision de schéma).
  - representant_nom, representant_prenom, representant_qualite : personne
    physique qui représente cette société associée (ex. son président).

Limite assumée, hors périmètre de cette migration : pas de CHECK forçant ces
champs quand type_personne='personne_morale' (ni les champs personne
physique quand ='personne_physique') -- suivrait la même absence de
contrainte déjà présente sur le reste de la table.

Revision ID: b2c4d6e8f0a2
Revises: a1c2d4e6f8b0
Create Date: 2026-09-21 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c4d6e8f0a2'
down_revision: Union[str, Sequence[str], None] = 'a1c2d4e6f8b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project_associates', sa.Column('denomination_sociale', sa.String(length=255), nullable=True))
    op.add_column('project_associates', sa.Column('type_societe', sa.String(length=60), nullable=True))
    op.add_column('project_associates', sa.Column('capital_social', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column('project_associates', sa.Column('siege_social', sa.Text(), nullable=True))
    op.add_column('project_associates', sa.Column('lieu_immatriculation', sa.String(length=120), nullable=True))
    op.add_column('project_associates', sa.Column('numero_siren', sa.String(length=9), nullable=True))
    op.add_column('project_associates', sa.Column('representant_nom', sa.String(length=120), nullable=True))
    op.add_column('project_associates', sa.Column('representant_prenom', sa.String(length=120), nullable=True))
    op.add_column('project_associates', sa.Column('representant_qualite', sa.String(length=120), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_associates', 'type_societe')
    op.drop_column('project_associates', 'representant_qualite')
    op.drop_column('project_associates', 'representant_prenom')
    op.drop_column('project_associates', 'representant_nom')
    op.drop_column('project_associates', 'numero_siren')
    op.drop_column('project_associates', 'lieu_immatriculation')
    op.drop_column('project_associates', 'siege_social')
    op.drop_column('project_associates', 'capital_social')
    op.drop_column('project_associates', 'denomination_sociale')

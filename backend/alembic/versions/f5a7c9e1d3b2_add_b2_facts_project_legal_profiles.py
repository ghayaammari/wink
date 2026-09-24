"""add B2 legal facts to project_legal_profiles (raison_d_etre, objectifs_ess, sigle, lieu_signature_statuts)

Service 1.1.4 (statuts SAS) — catégorie B2 de l'inventaire des 210 variables
(voir historique "avant de valider je veut apartir de", 22/09/2026).

Faits juridiques de la société, imprimés dans les statuts (art. 2 : raison
d'être / objectifs ESS ; art. 3 : sigle ; bloc signature : lieu de signature),
manquants sur `project_legal_profiles`. Décision de conception actée : PAS sur
`project_public_profiles` (table de vitrine / matching investisseur, dont
`public_summary` est un pitch marketing modifiable à volonté — fusionner un
engagement statutaire avec un texte de vente créerait un risque d'édition
accidentelle de la clause légale). Même famille et même table que
`objet_social` / `duree_societe` / `date_signature_statuts`, qui sont déjà des
faits uniques par projet produits par 1.1.4 et consommés aussi par 1.1.5.

Toutes colonnes NULLABLE : laissées vides jusqu'à leur saisie au fil du
questionnaire des statuts ; l'en-tête (art. 2/3) les rend exigibles selon le
choix des associés (ESS oui/non, sigle optionnel). Pas de CHECK inter-champs,
cohérent avec le reste de la table (objet_social/duree_societe n'en portent pas).
(réalisé par OPENCODE)

Revision ID: f5a7c9e1d3b2
Revises: d6b8a4f2e0c9
Create Date: 2026-09-23 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f5a7c9e1d3b2'
down_revision: Union[str, Sequence[str], None] = 'd6b8a4f2e0c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project_legal_profiles', sa.Column('raison_d_etre', sa.Text(), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('objectifs_ess', sa.Text(), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('sigle', sa.String(length=120), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('lieu_signature_statuts', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_legal_profiles', 'lieu_signature_statuts')
    op.drop_column('project_legal_profiles', 'sigle')
    op.drop_column('project_legal_profiles', 'objectifs_ess')
    op.drop_column('project_legal_profiles', 'raison_d_etre')
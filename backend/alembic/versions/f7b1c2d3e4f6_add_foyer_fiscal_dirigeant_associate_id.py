"""
add project_associates.foyer_fiscal_dirigeant_associate_id

Condition e21_immatriculation_fiscale — article 239 bis AB du CGI.

Éligibilité à l'option IR d'une société à l'IS : plus de 34 % des droits de
vote détenus par LES DIRIGEANTS ET LEUR FOYER FISCAL (conjoint/PACS/enfants à
charge, art. 6 CGI). La phase I1 gérait uniquement les dirigeants (Option A,
décision de conception) ; cette migration ajoute le maillage "foyer fiscal" :

- nouvelle colonne NULLABLE project_associates.foyer_fiscal_dirigeant_associate_id
  avec FK auto-référente → project_associates.id (ondelete SET NULL) ;
- NULL = l'associé ne fait partie d'aucun foyer fiscal de dirigeant ;
- renseignée = l'associé (conjoint/conjoint PACS/enfant à charge) est rattaché
  à la ligne de l'associé dirigeant cible.
La cible doit être est_dirigeant = true et appartenir au même projet — contraintes
validées au niveau service (associate_service), pas en base.
(réalisé par OPENCODE)

Revision ID: f7b1c2d3e4f6
Revises: e1b2c3d4e5f6
Create Date: 2026-09-14 23:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f7b1c2d3e4f6'
down_revision: Union[str, Sequence[str], None] = 'e1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'project_associates',
        sa.Column(
            'foyer_fiscal_dirigeant_associate_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('project_associates.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_associates', 'foyer_fiscal_dirigeant_associate_id')
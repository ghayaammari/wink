"""widen researcher_field_values.source and validation_status columns

Un stub `c3874844861f` (08/09/2026) avait déjà identifié ce besoin mais son
upgrade()/downgrade() étaient vides (jamais complété, jamais appliqué —
`alembic current` au 22/09/2026 confirme un seul head, `c1a2b3c4d5e6`, qui ne
passe pas par ce stub). Cette migration-ci part directement de la tête
réelle et corrige pour de vrai.

Bug constaté en conditions réelles le 22/09/2026 : une première extraction
HAL/OpenAlex sur un compte de test a échoué sur CHAQUE travail avec
`StringDataRightTruncation: value too long for type character varying(20)`
— `source='extracted_from_papers'` fait 21 caractères, un caractère de plus
que la colonne VARCHAR(20) d'origine. `validation_status` n'a pas le même
bug aujourd'hui (`'pending_confirmation'` fait exactement 20 caractères,
tient pile) mais est élargie par précaution en même temps, sans marge
sinon au moindre statut plus long ajouté au CHECK plus tard.

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3c4d5e6
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'researcher_field_values', 'source',
        existing_type=sa.String(length=20),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
    op.alter_column(
        'researcher_field_values', 'validation_status',
        existing_type=sa.String(length=20),
        type_=sa.String(length=30),
        existing_nullable=False,
        existing_server_default=sa.text("'pending_confirmation'::character varying"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'researcher_field_values', 'validation_status',
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default=sa.text("'pending_confirmation'::character varying"),
    )
    op.alter_column(
        'researcher_field_values', 'source',
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        existing_nullable=False,
    )

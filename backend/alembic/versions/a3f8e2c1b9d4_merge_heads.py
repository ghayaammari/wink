"""merge heads (entrepreneur/chercheur/investisseur + rgpd-aipd)

Revision ID: a3f8e2c1b9d4
Revises: 82a64157b35d, a1b2c3d4e5f6, f1a2b3c4d5e6
Create Date: 2026-09-19 00:00:00.000000

Migration de fusion pure (pas de changement de schema) — CORRECTIF du
19/09/2026 : la chaine Alembic avait diverge en 3 tetes distinctes
(constate en tracant chaque fichier via down_revision), probablement du
travail parallele sur entrepreneur/chercheur/investisseur jamais fusionne.
`alembic upgrade head` echoue avec plusieurs tetes presentes tant que cette
fusion n'existe pas. Trouve en preparant le service 3.3.12 (AI Act), qui a
besoin d'une base a tete unique pour y accrocher sa propre migration.
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'a3f8e2c1b9d4'
down_revision: Union[str, Sequence[str], None] = ('82a64157b35d', 'a1b2c3d4e5f6', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

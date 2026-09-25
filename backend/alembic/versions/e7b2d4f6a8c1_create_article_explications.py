"""create article_explications (+ fusion des 2 têtes Alembic)

Service 1.1.4 (statuts SAS) — étape 4 de la refonte du parcours
(24/09/2026) : explications des articles facultatifs affichées sur l'écran de
choix, générées par LLM puis relues (voir le modèle `article_explication.py`).

Fusion : le dépôt avait 2 têtes (`ac13c03bc345` merge_heads du 23/09 et
`d3f7a1c9e5b4`, branchée sur `acb040c7128a`) — `alembic upgrade head`
échouait avec « multiple heads ». Cette migration a les 2 comme parents et
remet la chaîne sur une seule tête ; aucune opération de fusion à faire en
base (les 2 branches touchent des tables différentes).

Revision ID: e7b2d4f6a8c1
Revises: ac13c03bc345, d3f7a1c9e5b4
Create Date: 2026-09-24 10:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e7b2d4f6a8c1"
down_revision: Union[str, Sequence[str], None] = ("ac13c03bc345", "d3f7a1c9e5b4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_explications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("code_facultatif", sa.String(length=80), nullable=False),
        sa.Column("texte", sa.Text(), nullable=False),
        sa.Column("statut_contenu", sa.String(length=20), nullable=False, server_default="extrait_automatique"),
        sa.Column("genere_le", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valide_le", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("document_type", "code_facultatif", name="uq_article_explications_document_code"),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_article_explications_statut_contenu",
        ),
    )


def downgrade() -> None:
    op.drop_table("article_explications")

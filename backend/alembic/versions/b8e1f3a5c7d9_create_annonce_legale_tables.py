"""create annonce légale tables (service 1.1.5)

- `legal_announcements` : annonce de constitution d'un projet (rédaction,
  validation, attestation déposée) — remplace `legal_announcement_transmissions`
  de la conception Groupe 5 (transmission automatique hors périmètre v1).
- `jal_reference` : journaux/SPEL habilités par département (référentiel).
- `legal_announcement_guides` : guides pratiques officiels pour le copilot.
- `documents.document_type` accepte 'attestation_annonce_legale'.

Aucune modification de `content_embeddings` : le domaine 'annonce_legale'
est déjà accepté par ck_content_embeddings_domaine.

Revision ID: b8e1f3a5c7d9
Revises: e7b2d4f6a8c1
Create Date: 2026-09-25 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b8e1f3a5c7d9"
down_revision: Union[str, Sequence[str], None] = "e7b2d4f6a8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOC_TYPES_AVANT = "document_type IN ('entrepreneur_idea', 'other', 'pacte_fondateurs', 'statuts')"
_DOC_TYPES_APRES = (
    "document_type IN ('entrepreneur_idea', 'other', 'pacte_fondateurs', 'statuts', "
    "'attestation_annonce_legale')"
)


def upgrade() -> None:
    # PostgreSQL ne permet pas d'altérer un CHECK en place : suppression + recréation.
    op.drop_constraint("ck_documents_document_type", "documents", type_="check")
    op.create_check_constraint("ck_documents_document_type", "documents", _DOC_TYPES_APRES)

    op.create_table(
        "legal_announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("texte_annonce", sa.Text(), nullable=False),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="genere"),
        sa.Column("date_generation", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_validation_utilisateur", sa.DateTime(timezone=True), nullable=True),
        sa.Column("journal_utilise", sa.String(length=255), nullable=True),
        sa.Column("date_publication", sa.Date(), nullable=True),
        sa.Column(
            "attestation_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "statut IN ('genere', 'valide_utilisateur', 'attestation_deposee')",
            name="ck_legal_announcements_statut",
        ),
    )

    op.create_table(
        "jal_reference",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nom_journal", sa.String(length=255), nullable=False),
        sa.Column("type_support", sa.String(length=10), nullable=False),
        sa.Column(
            "departements_couverts",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("lien_site", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("statut_contenu", sa.String(length=20), nullable=False, server_default="extrait_automatique"),
        sa.Column("collecte_le", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("derniere_verification", sa.Date(), nullable=True),
        sa.UniqueConstraint("source_url", name="uq_jal_reference_source_url"),
        sa.CheckConstraint("type_support IN ('papier', 'spel')", name="ck_jal_reference_type_support"),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_jal_reference_statut_contenu",
        ),
    )
    # Recherche « journaux du département X » : opérateur ANY/@> sur le tableau.
    op.create_index(
        "ix_jal_reference_departements",
        "jal_reference",
        ["departements_couverts"],
        postgresql_using="gin",
    )

    op.create_table(
        "legal_announcement_guides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_nom", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("titre", sa.Text(), nullable=False),
        sa.Column("sous_theme", sa.String(length=50), nullable=False),
        sa.Column("texte_brut", sa.Text(), nullable=False),
        sa.Column("statut_contenu", sa.String(length=20), nullable=False, server_default="extrait_automatique"),
        sa.Column("collecte_le", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("derniere_verification", sa.Date(), nullable=True),
        sa.UniqueConstraint("source_url", name="uq_legal_announcement_guides_source_url"),
        sa.CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_legal_announcement_guides_statut_contenu",
        ),
    )


def downgrade() -> None:
    op.drop_table("legal_announcement_guides")
    op.drop_index("ix_jal_reference_departements", table_name="jal_reference")
    op.drop_table("jal_reference")
    op.drop_table("legal_announcements")
    op.drop_constraint("ck_documents_document_type", "documents", type_="check")
    op.create_check_constraint("ck_documents_document_type", "documents", _DOC_TYPES_AVANT)

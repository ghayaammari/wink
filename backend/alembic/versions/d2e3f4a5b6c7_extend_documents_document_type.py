"""extend documents.document_type for generated documents

Service 1.1.13/1.1.4 (Groupe 5 — Incrément 1)

Le CHECK constraint ck_documents_document_type (I0) ne permettait que
'entrepreneur_idea'/'other' : un document généré de type 'pacte_fondateurs'
ou 'statuts' aurait été rejeté en base. Dette connue signalée dans 1.1.17
(coffre-fort documentaire) et confirmée lors de l'audit avant implémentation.

Valeurs ajoutées minimales pour le besoin actuel (1.1.13 pacte + 1.1.4 statuts).
Les futures valeurs de service (annonce_legale 1.1.5, dbe 1.1.6, ...) feront
l'objet d'une migration dédiée au moment de chaque service — les ajouter toutes
dès maintenant reviendrait à anticiper des types pas encore produits.
(réalisé par OPENCODE)

Revision ID: d2e3f4a5b6c7
Revises: f7b1c2d3e4f6
Create Date: 2026-09-15 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'f7b1c2d3e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostgreSQL ne permet pas d'ALTÉRER une contrainte CHECK en place : il faut la
    # supprimer puis la recréer avec la nouvelle liste de valeurs.
    op.drop_constraint('ck_documents_document_type', 'documents', type_='check')
    op.create_check_constraint(
        'ck_documents_document_type',
        'documents',
        "document_type IN ('entrepreneur_idea', 'other', 'pacte_fondateurs', 'statuts')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_documents_document_type', 'documents', type_='check')
    op.create_check_constraint(
        'ck_documents_document_type',
        'documents',
        "document_type IN ('entrepreneur_idea', 'other')",
    )
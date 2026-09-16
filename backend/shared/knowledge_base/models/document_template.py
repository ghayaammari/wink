"""Table `document_templates` — squelette structurel d'un document type (Phase
collecte, Groupe 5 — services 1.1.13 pacte / 1.1.4 statuts).

Une ligne = une section du document final, dans l'ordre (`ordre`). Le contenu de
chaque section est une référence polymorphe (`reference_type` + `reference_id`) :
- `legal_texts` (mentions obligatoires, ex. les 14 mentions obligatoires SAS),
- `contract_clauses_library` (clauses types),
- `donnee_projet` (données injectées depuis le projet, sans référence),
- `texte_statique` (section fixe).

Non vectorisée : c'est un squelette structurel, pas un contenu interrogeable.
`UNIQUE(document_type, ordre)` garantit un ordre unique par type de document.
(réalisé par OPENCODE)
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

# Valeurs fermées (schéma Groupe 5) — étendues si une nouvelle forme de section apparaît.
_TYPE_CONTENU = "('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', 'texte_statique')"
_REFERENCE_TYPE = "('legal_texts', 'contract_clauses_library')"


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    nom_section: Mapped[str] = mapped_column(String(255), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    type_contenu: Mapped[str] = mapped_column(String(40), nullable=False)
    # Référence polymorphe : pas de vraie contrainte FK possible en PostgreSQL vers
    # l'une OU l'autre table cible — reference_type dit où pointer, reference_id l'id.
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Si false, l'utilisateur choisit d'inclure la section ou non à la génération.
    obligatoire: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    forme_juridique_concernee: Mapped[str | None] = mapped_column(String(60), nullable=True)
    texte_statique: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("document_type", "ordre", name="uq_document_templates_type_ordre"),
        CheckConstraint(f"type_contenu IN {_TYPE_CONTENU}", name="ck_document_templates_type_contenu"),
        CheckConstraint(f"reference_type IN {_REFERENCE_TYPE}", name="ck_document_templates_reference_type"),
    )
"""Table `documents` — métadonnées des fichiers importés par l'utilisateur.

Le binaire reste sur Cloudinary, jamais en base : cette table ne stocke que le
suivi (statut, visibilité, version courante) ; le contenu réel est dans
`document_versions`.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private")
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="uploaded")
    # FK circulaire documents <-> document_versions (document_versions.document_id -> documents.id) :
    # use_alter=True pour que SQLAlchemy crée les deux tables puis ajoute cette FK par ALTER TABLE.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", use_alter=True, name="fk_documents_current_version_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Valeurs étendues par le Groupe 5 (migration d2e3f4a5b6c7) : les documents générés
        # par 1.1.13 (pacte de fondateurs) et 1.1.4 (statuts) sont stockés ici comme les
        # imports I0. 'attestation_annonce_legale' ajoutée par 1.1.5 (migration b8e1f3a5c7d9,
        # attestation de parution déposée par l'entrepreneur). D'autres valeurs de service suivront aux incréments concernés
        # (annonce légale 1.1.5, DBE 1.1.6, etc.) — chaque extension passe par une migration.
        CheckConstraint(
            "document_type IN ('entrepreneur_idea', 'other', 'pacte_fondateurs', 'statuts', "
            "'attestation_annonce_legale')",
            name="ck_documents_document_type",
        ),
        CheckConstraint("visibility IN ('private', 'project_members')", name="ck_documents_visibility"),
        CheckConstraint(
            "processing_status IN ('uploaded', 'queued', 'processing', 'ready', 'failed')",
            name="ck_documents_processing_status",
        ),
    )

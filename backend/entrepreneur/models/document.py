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
        CheckConstraint("document_type IN ('entrepreneur_idea', 'other')", name="ck_documents_document_type"),
        CheckConstraint("visibility IN ('private', 'project_members')", name="ck_documents_visibility"),
        CheckConstraint(
            "processing_status IN ('uploaded', 'queued', 'processing', 'ready', 'failed')",
            name="ck_documents_processing_status",
        ),
    )

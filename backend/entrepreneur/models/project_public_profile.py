"""Table `project_public_profiles` — vitrine publique du projet (affichage externe, ex: matching investisseur)."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectPublicProfile(Base):
    __tablename__ = "project_public_profiles"
    __table_args__ = (
        CheckConstraint(
            "funding_visibility IN ('private', 'public', 'investors_only')",
            name="ck_project_public_profiles_funding_visibility",
        ),
        CheckConstraint(
            "compliance_visibility IN ('private', 'public', 'investors_only')",
            name="ck_project_public_profiles_compliance_visibility",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    public_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    public_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # URL Cloudinary directe (image), pas de FK vers documents/document_versions.
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    funding_visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private")
    compliance_visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

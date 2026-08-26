"""Table `project_legal_profiles` — identité légale du projet (pour les startups déjà créées)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectLegalProfile(Base):
    __tablename__ = "project_legal_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    is_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True, index=True)
    siret: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    vat_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    naf_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    legal_representative: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

"""Table `project_field_values` — traçabilité de chaque champ extrait automatiquement, avec sa confirmation."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectFieldValue(Base):
    __tablename__ = "project_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_source: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="en_attente")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "field_name", name="uq_project_field_values_project_id_field_name"),
        CheckConstraint(
            "extraction_source IN ('extrait_automatique', 'saisi_par_utilisateur')",
            name="ck_project_field_values_extraction_source",
        ),
        CheckConstraint(
            "validation_status IN ('en_attente', 'confirme', 'corrige')",
            name="ck_project_field_values_validation_status",
        ),
    )

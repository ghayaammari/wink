"""Table `projects` — l'idée ou la startup présentée par l'entrepreneur."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    entrepreneur_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entrepreneur_profiles.id", ondelete="CASCADE"), nullable=False
    )
    project_type: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    # Nullable : dans le parcours du questionnaire (service 0.0.2/0.0.3), le projet est créé à
    # l'écran 2 (project_type + stage seulement) et ces deux champs ne sont répondus qu'à
    # l'écran 4 — il existe un vrai état transitoire "pas encore répondu" entre les deux.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # FK circulaire projects <-> documents (documents.project_id -> projects.id) :
    # use_alter=True pour que SQLAlchemy crée les deux tables puis ajoute cette FK par ALTER TABLE.
    imported_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", use_alter=True, name="fk_projects_imported_document_id"),
        nullable=True,
    )
    nombre_cofondateurs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intention_levee_fonds: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    localisation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subsectors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    customer_segments: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    target_users: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    value_proposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_profile_completion: Mapped[str] = mapped_column(String(20), nullable=False, server_default="incomplet")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("project_type IN ('not_created', 'created')", name="ck_projects_project_type"),
        CheckConstraint("stage IN ('ideation', 'pre_seed', 'seed', 'serie_a')", name="ck_projects_stage"),
        CheckConstraint(
            "source_type IN ('texte_libre', 'document_importe')", name="ck_projects_source_type"
        ),
        CheckConstraint(
            "source_type <> 'document_importe' OR imported_document_id IS NOT NULL",
            name="ck_projects_imported_document_required",
        ),
        CheckConstraint(
            "project_profile_completion IN ('incomplet', 'complet')",
            name="ck_projects_profile_completion",
        ),
    )

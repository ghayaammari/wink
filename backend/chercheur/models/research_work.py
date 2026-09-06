"""Table `research_works` — travaux du chercheur.

Les métadonnées bibliographiques brutes sont des colonnes directes ; les
interprétations générées par LLM à partir du contenu passent par
`researcher_field_values` (paper_summary, methodology, key_findings,
application_domains).

Règle métier : un dépôt manuel (`source_type = depot_manuel`) est toujours
`private_matching_only` et `confirmed` par construction — pas d'étape de
validation supplémentaire. Seuls les travaux `extrait_hal_openalex` suivent
le cycle complet de validation.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.shared.database import Base

if TYPE_CHECKING:
    from backend.chercheur.models.researcher_profile import ResearcherProfile


class ResearchWork(Base):
    __tablename__ = "research_works"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    researcher_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)  # fourni par les auteurs, distinct de paper_summary
    authors: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # fait bibliographique brut
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # dépôt manuel

    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending_confirmation")
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private_matching_only")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    researcher_profile: Mapped["ResearcherProfile"] = relationship(back_populates="research_works")

    __table_args__ = (
        CheckConstraint(
            "publication_type IN ('article', 'communication', 'these', 'brevet', 'rapport')",
            name="ck_research_works_publication_type",
        ),
        CheckConstraint(
            "source_type IN ('extrait_hal_openalex', 'depot_manuel')",
            name="ck_research_works_source_type",
        ),
        CheckConstraint(
            "validation_status IN ('pending_confirmation', 'confirmed', 'rejected')",
            name="ck_research_works_validation_status",
        ),
        CheckConstraint(
            "visibility IN ('public_profile', 'private_matching_only')",
            name="ck_research_works_visibility",
        ),
        CheckConstraint(
            "source_type != 'depot_manuel' OR file_url IS NOT NULL",
            name="ck_research_works_file_url_required_if_manual",
        ),
    )

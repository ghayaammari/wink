"""Table `researcher_profiles` — profil du chercheur.

`affiliation` et `research_domains` sont matérialisés ici après validation
via `researcher_field_values` — jamais saisis directement en dehors du
mécanisme polymorphe. `expertise_summary` et `research_work_summary` sont
deux résumés distincts, générés automatiquement, jamais saisis.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.shared.database import Base

if TYPE_CHECKING:
    from backend.chercheur.models.research_work import ResearchWork
    from backend.chercheur.models.researcher_past_expertise import ResearcherPastExpertise
    from backend.chercheur.models.research_axis_follow import ResearchAxisFollow


class ResearcherProfile(Base):
    __tablename__ = "researcher_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Saisi directement (étape 5 de l'onboarding, si Extraire/Les deux)
    orcid_id: Mapped[str | None] = mapped_column(String(19), nullable=True)

    # Matérialisés depuis researcher_field_values une fois confirmés — jamais écrits ailleurs
    affiliation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    research_domains: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # Pilotage de l'import asynchrone (extraction HAL/OpenAlex)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="not_started")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Générés après coup, jamais saisis
    expertise_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_work_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_completion: Mapped[str] = mapped_column(String(20), nullable=False, server_default="incomplet")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relations — lecture pratique depuis le profil, pas de logique métier ici
    research_works: Mapped[list["ResearchWork"]] = relationship(
        back_populates="researcher_profile", cascade="all, delete-orphan"
    )
    past_expertises: Mapped[list["ResearcherPastExpertise"]] = relationship(
        back_populates="researcher_profile", cascade="all, delete-orphan"
    )
    axis_follows: Mapped[list["ResearchAxisFollow"]] = relationship(
        back_populates="researcher_profile", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "sync_status IN ('not_started', 'queued', 'in_progress', 'completed', 'failed')",
            name="ck_researcher_profiles_sync_status",
        ),
        CheckConstraint(
            "profile_completion IN ('incomplet', 'complet')",
            name="ck_researcher_profiles_profile_completion",
        ),
    )

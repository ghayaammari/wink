"""Table `researcher_past_expertises` — expertises/missions de conseil
réalisées par le chercheur avant son inscription sur Wink.

Table facultative : zéro ligne si le chercheur n'a jamais fait d'expertise.
Alimente `researcher_profiles.expertise_summary` une fois qu'au moins une
ligne existe. Jamais demandée pendant l'onboarding — accessible depuis le
profil à tout moment.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.shared.database import Base

if TYPE_CHECKING:
    from backend.chercheur.models.researcher_profile import ResearcherProfile


class ResearcherPastExpertise(Base):
    __tablename__ = "researcher_past_expertises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    researcher_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )

    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(160), nullable=True)
    mission_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(60), nullable=True)  # période en texte libre
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    researcher_profile: Mapped["ResearcherProfile"] = relationship(back_populates="past_expertises")

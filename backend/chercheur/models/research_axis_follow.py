"""Table `research_axis_follows` — axes thématiques que le chercheur choisit
de suivre, pour être notifié dès qu'un appel à projets correspondant est
publié (service 0.0.5).

Pas de `updated_at` : un axe suivi se retire (suppression de la ligne)
plutôt qu'il ne se renomme en place.

⚠️ Point signalé comme "à confirmer" dans le schéma source — si un besoin de
renommage en place apparaît plus tard, il faudra ajouter `updated_at` via
migration plutôt que de forcer un contournement applicatif (suppression +
recréation perd l'historique `created_at`).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from backend.shared.database import Base

if TYPE_CHECKING:
    from backend.chercheur.models.researcher_profile import ResearcherProfile


class ResearchAxisFollow(Base):
    __tablename__ = "research_axis_follows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    researcher_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    axis_label: Mapped[str] = mapped_column(String(160), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    researcher_profile: Mapped["ResearcherProfile"] = relationship(back_populates="axis_follows")

    __table_args__ = (
        UniqueConstraint("researcher_profile_id", "axis_label", name="uq_research_axis_follows_profile_label"),
    )

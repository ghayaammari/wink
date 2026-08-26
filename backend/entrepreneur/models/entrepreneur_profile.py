"""Table `entrepreneur_profiles` — table fine de liaison user <-> rôle entrepreneur.

Ne porte aucun champ métier : tous les faits déclaratifs appartiennent au projet
(`Project`), pas à la personne. Ouvre la possibilité qu'un même entrepreneur
porte plusieurs projets à l'avenir, sans changement de structure supplémentaire.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class EntrepreneurProfile(Base):
    __tablename__ = "entrepreneur_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

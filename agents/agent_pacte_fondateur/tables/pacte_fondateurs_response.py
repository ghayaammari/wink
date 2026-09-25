"""Table `pacte_fondateurs_responses` -- la reponse du copilot a un message,
toujours 1:1 (message_id UNIQUE) -- une question n'a jamais deux reponses.

Voir docstring de pacte_fondateurs_conversation.py pour l'isolation
volontaire de ce dossier.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class PacteFondateursResponse(Base):
    __tablename__ = "pacte_fondateurs_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pacte_fondateurs_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    reponse: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("message_id", name="uq_pacte_fondateurs_responses_message_id"),
    )

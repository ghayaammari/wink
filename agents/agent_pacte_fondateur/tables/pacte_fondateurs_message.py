"""Table `pacte_fondateurs_messages` -- une question posee par l'utilisateur
dans la bulle du copilot pacte de fondateurs.

`code_clause_contexte` (nullable) : la clause affichee sur la page au moment
de la question (ex: "inalienabilite_fondateurs_partielle_plafond"), NULL si
la question est posee hors contexte de clause (question generale sur le
pacte). Absent du schema officiel copilot_messages (question TEXT seul) --
ajoute ici car necessaire au besoin "expliquer cette clause" (contexte de
page), voir discussion architecture 22/09/2026.

Voir docstring de pacte_fondateurs_conversation.py pour l'isolation
volontaire de ce dossier.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class PacteFondateursMessage(Base):
    __tablename__ = "pacte_fondateurs_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pacte_fondateurs_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    code_clause_contexte: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

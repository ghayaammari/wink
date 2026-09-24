"""Table `pacte_fondateurs_conversations` -- fil de discussion persistant du
copilot pacte de fondateurs (service 1.1.13, categorie 3). Un seul fil par
projet (UniqueConstraint project_id) -- pas de notion de conversations
multiples nommees, voir docstring de la migration pour le pourquoi.

ISOLATION VOLONTAIRE : ce dossier (agents/agent_pacte_fondateur/) regroupe
tout le travail de cet agent -- tables comprises -- en dehors de
`Wink_architecture_fichiers.md` (qui voudrait ces tables sous
backend/shared/knowledge_base/models/ ou backend/entrepreneur/models/).
Decision actee avec l'utilisateur (22/09/2026) : la binome travaille en
parallele sur un agent copilot (Groupe 3, code pas encore pushe) -- isoler
completement ce travail evite toute collision au pull, au prix d'une vraie
migration a faire plus tard pour fusionner avec son code.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class PacteFondateursConversation(Base):
    __tablename__ = "pacte_fondateurs_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_pacte_fondateurs_conversations_project_id"),
    )

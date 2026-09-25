"""Table `project_ai_act_obligations_history` — service 3.3.12 (AI Act).

Copie conforme de `project_rgpd_obligation_history.py` : snapshot figé,
alimentée uniquement lors d'une régénération majeure (changement significatif
de `ai_act_data_profile`), même raisonnement, non répété ici.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectAiActObligationHistory(Base):
    __tablename__ = "project_ai_act_obligations_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("statut IN ('a_faire', 'fait')", name="ck_project_ai_act_obligations_history_statut"),
    )

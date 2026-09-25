"""Table `project_rgpd_obligations_history` — service 3.3.1 (RGPD). Archive
des obligations remplacées, alimentée UNIQUEMENT lors d'une régénération
majeure de `project_rgpd_obligations` suite à un changement significatif du
profil (voir compliance_data_profile) — pas à chaque petite modification.

Snapshot figé (pas de FK vivante vers project_rgpd_obligations : la ligne
d'origine est remplacée/supprimée, ce tableau garde une copie autonome de ce
qui existait avant). Décision actée : solution pragmatique plutôt qu'un
système de versionning complet — dette technique assumée si les changements
de profil deviennent fréquents (perte de continuité du statut `fait` sur
régénération complète, voir project_rgpd_obligation.py).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectRgpdObligationHistory(Base):
    __tablename__ = "project_rgpd_obligations_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Copie du nom/description/statut au moment de l'archivage — pas de FK
    # vers legal_texts non plus, snapshot complet et autonome (voir docstring).
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False)
    # Copie de project_rgpd_obligations.lie_a_aipd au moment de l'archivage -
    # meme principe de snapshot autonome que les autres colonnes ci-dessus.
    lie_a_aipd: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("statut IN ('a_faire', 'fait')", name="ck_project_rgpd_obligations_history_statut"),
    )

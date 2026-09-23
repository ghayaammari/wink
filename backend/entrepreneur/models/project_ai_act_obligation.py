"""Table `project_ai_act_obligations` — service 3.3.12 (AI Act). Copie

conforme de `project_rgpd_obligation.py` (service 3.3.1), même raisonnement
("table vivante", pas de catalogue intermédiaire, correspondance par `nom`
en dette technique assumée) : voir ce fichier pour le détail des décisions,
non répétées ici.

Seule différence avec le RGPD : pas d'équivalent au flag `lie_a_aipd` — l'AI
Act n'a pas de sous-processus comparable à l'AIPD nécessitant un
regroupement visuel à part. À ajouter uniquement si un besoin de
regroupement réel apparaît plus tard (même règle que documentée dans
project_rgpd_obligation.py : pas de taxonomie anticipée sans besoin concret).

Règle "jamais écraser un fait" : identique au RGPD (voir
project_rgpd_obligation_service.py, à écrire pour l'AI Act sur le même
modèle).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectAiActObligation(Base):
    __tablename__ = "project_ai_act_obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="a_faire")
    legal_text_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_texts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "nom", name="uq_project_ai_act_obligations_project_nom"),
        CheckConstraint("statut IN ('a_faire', 'fait')", name="ck_project_ai_act_obligations_statut"),
    )

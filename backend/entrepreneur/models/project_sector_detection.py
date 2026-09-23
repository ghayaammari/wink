"""Table `project_sector_detection` — service 3.3.5 (Diagnostic de

classification réglementaire), étape 0 : détection du secteur réglementé
avant même de choisir quel questionnaire (HealthTech ou FinTech) proposer.

1 ligne par projet (UniqueConstraint project_id), `secteur_detecte=NULL` tant
que la détection n'a jamais été lancée (voir sector_detection_service.py,
agents/compliance_agent/) — même convention que project_ai_act_classification.

Scope volontairement limité à 2 secteurs pour cet incrément (décision du
19/09/2026) : `projects.sector` est un champ texte libre non normalisé
(String(120), pas de liste fixe côté onboarding), donc la détection passe
par un appel LLM plutôt qu'une correspondance exacte sur ce texte — voir
sector_detection_service.py pour le raisonnement complet.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectSectorDetection(Base):
    __tablename__ = "project_sector_detection"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = detection jamais lancee. 'aucun' = ni healthtech ni fintech,
    # valeur explicite distincte de NULL (voir CheckConstraint ci-dessous).
    secteur_detecte: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_sector_detection_project_id"),
        CheckConstraint(
            "secteur_detecte IN ('healthtech', 'fintech', 'aucun')",
            name="ck_project_sector_detection_secteur_detecte",
        ),
    )

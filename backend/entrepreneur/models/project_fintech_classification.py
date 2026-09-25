"""Table `project_fintech_classification` — service 3.3.5, résultat de la

classification FinTech (type d'agrément au sens du Code monétaire et
financier / ACPR). 1 ligne par projet, NULL tant qu'aucune classification
n'a été calculée.

Comme pour HealthTech, calcul déterministe en Python (pas de LLM) — voir
project_fintech_classification_service.py::classify() et la docstring de
project_healthtech_classification.py pour le raisonnement complet.

Simplification assumée (dette technique documentée) : le document de
cadrage mentionne une possible "exemption" en plus de l'agrément simplifié
et classique, mais sans seuil exploitable pour la produire de façon fiable
— valeur volontairement absente du CheckConstraint tant qu'un critère
concret n'est pas défini, plutôt que d'ajouter une valeur que le code ne
saura jamais renvoyer.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectFintechClassification(Base):
    __tablename__ = "project_fintech_classification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type_agrement: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_fintech_classification_project_id"),
        CheckConstraint(
            "type_agrement IN ('aucun', 'agrement_simplifie', 'agrement_classique')",
            name="ck_project_fintech_classification_type_agrement",
        ),
    )

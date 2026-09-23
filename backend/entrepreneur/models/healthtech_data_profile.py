"""Table `healthtech_data_profile` — service 3.3.5, questionnaire tri-état

spécifique HealthTech. Même mécanisme que `ai_act_data_profile.py` :
`bool | None`, `None` = pas encore répondu, PATCH via `exclude_unset=True`
côté service.

Chaîne séquentielle voulue (voir project_healthtech_classification_service.py) :
`est_dispositif_medical` est le champ "porte" (comme `utilise_ia` pour l'AI
Act) — si `False`, la classe est `non_dispositif_medical` sans regarder les
3 champs suivants. `fournit_aide_decision_diagnostique_ou_therapeutique` est
une 2e porte : si `False` (dispositif médical mais sans rôle décisionnel
clinique), classe `I` sans regarder les 2 derniers champs, qui ne servent
qu'à distinguer IIa / IIb / III.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class HealthtechDataProfile(Base):
    __tablename__ = "healthtech_data_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    est_dispositif_medical: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fournit_aide_decision_diagnostique_ou_therapeutique: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risque_deces_ou_deterioration_irreversible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risque_intervention_chirurgicale_ou_deterioration_grave: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("project_id", name="uq_healthtech_data_profile_project_id"),)

"""Table `fintech_data_profile` — service 3.3.5, questionnaire tri-état

spécifique FinTech. Même mécanisme que les autres profils sectoriels :
`bool | None`, `None` = pas encore répondu.

`gere_fonds_ou_paiements_clients` est le champ "porte" (comme
`est_dispositif_medical` pour HealthTech) : si `False`, type d'agrément
`aucun` sans regarder les 3 champs suivants.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class FintechDataProfile(Base):
    __tablename__ = "fintech_data_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    gere_fonds_ou_paiements_clients: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    volume_mensuel_depasse_3_millions: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    propose_transmission_de_fonds: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gere_investissement_ou_actifs: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("project_id", name="uq_fintech_data_profile_project_id"),)

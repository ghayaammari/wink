"""Table `name_availability_checks` — historique des noms testés par
l'entrepreneur pour le service 1.1.2 (vérificateur croisé de disponibilité du
nom). Plusieurs vérifications possibles par projet, aucune contrainte
d'unicité : un même nom peut être re-testé (voir page Notion "Schemas grp 4").
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class NameAvailabilityCheck(Base):
    __tablename__ = "name_availability_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    nom_teste: Mapped[str] = mapped_column(String(255), nullable=False)
    statut_denomination: Mapped[str] = mapped_column(String(20), nullable=False)
    statut_marque: Mapped[str] = mapped_column(String(20), nullable=False)
    verifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "statut_denomination IN ('disponible', 'pris')",
            name="ck_name_availability_checks_statut_denomination",
        ),
        CheckConstraint(
            "statut_marque IN ('disponible', 'risque', 'pris')",
            name="ck_name_availability_checks_statut_marque",
        ),
    )

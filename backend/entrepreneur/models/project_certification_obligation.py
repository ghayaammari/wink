"""Table `project_certification_obligations` — service 3.3.11 (Accompagnement

accéléré vers les certifications de sécurité : ISO 27001, SOC 2,
SecNumCloud). Même principe "table vivante" que ProjectRgpdObligation : 1
ligne par étape du parcours de certification applicable à un projet, statut
coché manuellement par l'entrepreneur, jamais écrasé par une régénération
(logique portée par le service, pas par ce modèle).

Différence avec ProjectRgpdObligation : `type_certification` (V1 limitée à
'secnumcloud' -- seule certification avec un référentiel public exploitable,
voir migration q4d6f8a0b2c4 ; ISO 27001/SOC 2 s'ajouteront plus tard en
étendant la CheckConstraint, pas en créant une nouvelle table) et `ordre`
(contrairement aux obligations RGPD, les étapes d'une certification suivent
un vrai parcours séquentiel : gap analysis avant audit blanc avant audit de
certification).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectCertificationObligation(Base):
    __tablename__ = "project_certification_obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type_certification: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Position dans le parcours (0, 1, 2...) -- affichage ordonné côté
    # frontend, jamais recalculé par tri alphabétique sur `nom`.
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="a_faire")
    legal_text_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_texts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "type_certification", "nom", name="uq_project_certification_obligations_project_type_nom"
        ),
        CheckConstraint(
            "type_certification IN ('secnumcloud')",
            name="ck_project_certification_obligations_type",
        ),
        CheckConstraint("statut IN ('a_faire', 'fait')", name="ck_project_certification_obligations_statut"),
    )

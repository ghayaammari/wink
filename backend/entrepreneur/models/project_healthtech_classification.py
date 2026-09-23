"""Table `project_healthtech_classification` — service 3.3.5, résultat de la

classification HealthTech (classe de risque au sens du règlement MDR
2017/745). 1 ligne par projet, NULL tant qu'aucune classification n'a été
calculée.

Contrairement à l'AI Act, ce résultat n'est PAS produit par un LLM : les
règles de classification MDR citées dans le document de cadrage (classe IIa
par défaut pour une décision diagnostique/thérapeutique, escaladée en IIb/III
selon la gravité) sont un arbre de décision fermé sur 4 booléens connus à
l'avance — un calcul Python déterministe est plus fiable qu'un appel LLM ici
(zéro risque d'hallucination, zéro coût, résultat instantané), voir
project_healthtech_classification_service.py::classify(). Le LLM reste la
bonne solution pour l'AI Act/RGPD car leurs obligations sont extraites d'un
corpus de texte libre, pas d'un arbre de règles fermé.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectHealthtechClassification(Base):
    __tablename__ = "project_healthtech_classification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    classe_risque: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_healthtech_classification_project_id"),
        CheckConstraint(
            "classe_risque IN ('non_dispositif_medical', 'I', 'IIa', 'IIb', 'III')",
            name="ck_project_healthtech_classification_classe_risque",
        ),
    )

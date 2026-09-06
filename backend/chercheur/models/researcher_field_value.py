"""Table `researcher_field_values` — mécanisme polymorphe de traçabilité.

Applicable au profil du chercheur (`researcher_profiles`) et à un papier
précis (`research_works`), distingués par `entity_type`/`entity_id`. Une
fois confirmée, une valeur est matérialisée sur la table d'origine pour une
lecture rapide sans jointure.

Règles métier (appliquées côté service, pas en contrainte DB) :
- Si `source = user_added` → `validation_status = confirmed` directement.
- Pour un champ à valeur unique, quand une nouvelle valeur candidate est
  confirmée, l'ancienne ligne `confirmed` passe automatiquement à `superseded`.

Note : `field_name` n'a pas de CheckConstraint SQL car les valeurs valides
dépendent de `entity_type` (contrainte conditionnelle) :
- Sur researcher_profile : research_domains (multi-valeur), affiliation,
  expertise_summary, research_work_summary (valeur unique)
- Sur research_work : paper_summary, methodology, key_findings (valeur
  unique), application_domains (multi-valeur)
Cette validation est faite au niveau du schéma Pydantic / service.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ResearcherFieldValue(Base):
    __tablename__ = "researcher_field_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Polymorphisme — pas de FK réelle possible ici, entity_id pointe vers
    # researcher_profiles.id ou research_works.id selon entity_type
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending_confirmation")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "field_name", "field_value", name="uq_researcher_field_values"),
        CheckConstraint(
            "entity_type IN ('researcher_profile', 'research_work')",
            name="ck_researcher_field_values_entity_type",
        ),
        CheckConstraint(
            "source IN ('extracted_from_papers', 'user_added', 'llm_generated', 'llm_analysis')",
            name="ck_researcher_field_values_source",
        ),
        CheckConstraint(
            "validation_status IN ('pending_confirmation', 'confirmed', 'rejected', 'superseded')",
            name="ck_researcher_field_values_validation_status",
        ),
    )

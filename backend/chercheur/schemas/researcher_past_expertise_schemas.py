"""Schémas Pydantic — researcher_past_expertises. Service optionnel : le
chercheur déclare ses expertises passées librement depuis son profil, jamais
demandé à l'onboarding (voir researcher_past_expertise.py). Pas de mécanisme
de validation via researcher_field_values ici — contrairement aux champs
extraits de HAL/OpenAlex, ce sont des données saisies directement par le
chercheur, donc confirmées par construction (même logique que source=user_added
sur les autres tables).
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PastExpertiseCreate(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=160)
    mission_type: str | None = Field(default=None, max_length=60)
    period_label: str | None = Field(default=None, max_length=60)
    description: str | None = None


class PastExpertiseUpdate(BaseModel):
    # Tous optionnels — mise à jour partielle (model_dump(exclude_unset=True)
    # côté service), même logique que ResearchWorkUpdate côté research_works.
    organization_name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=160)
    mission_type: str | None = Field(default=None, max_length=60)
    period_label: str | None = Field(default=None, max_length=60)
    description: str | None = None


class PastExpertiseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    researcher_profile_id: uuid.UUID
    organization_name: str
    domain: str | None
    mission_type: str | None
    period_label: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
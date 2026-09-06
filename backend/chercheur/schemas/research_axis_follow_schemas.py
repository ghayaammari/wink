"""Schémas Pydantic — research_axis_follows.

Service 0.0.5. Pas de schéma "Update" — un axe suivi se retire, il ne se
renomme pas en place (cohérent avec l'absence d'updated_at sur le modèle).
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AxisFollowCreate(BaseModel):
    axis_label: str = Field(..., min_length=1, max_length=160)


class AxisFollowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    researcher_profile_id: uuid.UUID
    axis_label: str
    created_at: datetime

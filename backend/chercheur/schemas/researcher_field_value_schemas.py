"""Schémas Pydantic — researcher_field_values.

Utilisé pour deux flux : lecture des valeurs en attente (côté profil ou côté
papier), et action de validation (confirmer/rejeter) sur une ligne précise.
"""
import uuid
from datetime import datetime
from typing import Literal
from typing import Literal, Optional
from pydantic import BaseModel, field_validator

from pydantic import BaseModel, ConfigDict


class ResearcherFieldValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: Literal["researcher_profile", "research_work"]
    entity_id: uuid.UUID
    field_name: str
    field_value: str
    source: Literal["extracted_from_papers", "user_added", "llm_generated", "llm_analysis"]
    validation_status: Literal["pending_confirmation", "confirmed", "rejected", "superseded"]
    created_at: datetime
    updated_at: datetime


from typing import Literal, Optional
from pydantic import BaseModel, field_validator

class ResearcherFieldValueValidationAction(BaseModel):
    action: Literal["confirm", "reject", "edit"]
    new_value: Optional[str] = None

    @field_validator("new_value")
    @classmethod
    def new_value_required_for_edit(cls, v, info):
        if info.data.get("action") == "edit" and not (v and v.strip()):
            raise ValueError("new_value est requis et non vide pour l'action 'edit'")
        return v

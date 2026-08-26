"""Schémas Pydantic pour `entrepreneur_profiles`.

Table de liaison sans champ métier — créée automatiquement par le service
d'auth au choix du rôle "entrepreneur" (voir backend/shared/auth). Aucun
schéma Create/Update côté client : uniquement un schéma de lecture.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntrepreneurProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

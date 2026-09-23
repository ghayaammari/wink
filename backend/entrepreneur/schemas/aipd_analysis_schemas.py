"""Schémas Pydantic pour `aipd_analyses` — service 3.3.4 (AIPD)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AipdAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    project_rgpd_obligation_id: UUID | None
    contenu: str
    generated_at: datetime

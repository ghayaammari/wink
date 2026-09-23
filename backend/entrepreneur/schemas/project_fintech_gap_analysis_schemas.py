"""Schémas Pydantic pour `project_fintech_gap_analysis` (service 3.3.6,

volet FinTech) — un seul schéma de lecture, pas d'équivalent à
ChapitreGapAnalysisStatusRead (HealthTech) : aucun chapitre, aucun statut de
verrouillage à représenter ici, voir docstring du modèle.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ObligationToggleUpdate(BaseModel):
    """Même rôle que son homonyme côté HealthTech

    (project_healthtech_gap_analysis_schemas.py)."""

    accompli: bool


class ProjectFintechGapAnalysisRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    project_id: UUID
    obligations: dict
    justification: str
    created_at: datetime
    updated_at: datetime

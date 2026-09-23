"""Schémas Pydantic pour `project_healthtech_gap_analysis` (service 3.3.6,
volet HealthTech) — même dossier/convention que
project_healthtech_classification_schemas.py.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ChapitreHealthtech = Literal["obligations_fabricant", "evaluation_clinique", "surveillance_post_commercialisation"]

StatutChapitre = Literal["verrouille", "debloque", "fait"]


class ProjectHealthtechGapAnalysisRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    project_id: UUID
    chapitre: ChapitreHealthtech
    obligations: dict
    justification: str
    created_at: datetime
    updated_at: datetime


class ObligationToggleUpdate(BaseModel):
    """Corps du PATCH qui bascule le suivi manuel "accompli" d'une

    obligation — pur suivi côté entrepreneur, aucun recalcul déclenché."""

    accompli: bool


class ChapitreGapAnalysisStatusRead(BaseModel):
    """Un élément de la mini-roadmap affichée côté frontend — statut calculé

    à la lecture (voir project_healthtech_gap_analysis_service.py), jamais
    stocké tel quel."""

    cle: ChapitreHealthtech
    titre: str
    statut: StatutChapitre
    resultat: ProjectHealthtechGapAnalysisRead | None = None

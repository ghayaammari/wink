"""Schémas Pydantic pour `project_sector_detection` — service 3.3.5, étape 0

(détection du secteur réglementé). `SecteurDetecte` reprend exactement les
3 valeurs du CheckConstraint du modèle (voir docstring de
`project_sector_detection.py` pour le raisonnement de cohérence).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

SecteurDetecte = Literal["healthtech", "fintech", "aucun"]


class ProjectSectorDetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    # None tant que la detection n'a jamais ete lancee (voir docstring modele).
    secteur_detecte: SecteurDetecte | None
    justification: str | None
    created_at: datetime
    updated_at: datetime

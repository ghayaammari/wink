"""Schémas Pydantic pour `project_fintech_classification` — service 3.3.5

(FinTech). `TypeAgrementFintech` reprend exactement les 3 valeurs du
CheckConstraint du modèle (voir docstring de
`project_fintech_classification.py` pour le raisonnement de cohérence,
notamment la simplification assumée sur l'exemption).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

TypeAgrementFintech = Literal["aucun", "agrement_simplifie", "agrement_classique"]


class ProjectFintechClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    # None tant que la classification n'a jamais ete calculee (voir docstring modele).
    type_agrement: TypeAgrementFintech | None
    justification: str | None
    created_at: datetime
    updated_at: datetime

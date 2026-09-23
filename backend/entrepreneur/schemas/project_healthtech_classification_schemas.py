"""Schémas Pydantic pour `project_healthtech_classification` — service 3.3.5

(HealthTech). `ClasseRisqueHealthtech` reprend exactement les 5 valeurs du
CheckConstraint du modèle (voir docstring de
`project_healthtech_classification.py` pour le raisonnement de cohérence,
notamment le choix d'un calcul déterministe plutôt qu'un LLM).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ClasseRisqueHealthtech = Literal["non_dispositif_medical", "I", "IIa", "IIb", "III"]


class ProjectHealthtechClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    # None tant que la classification n'a jamais ete calculee (voir docstring modele).
    classe_risque: ClasseRisqueHealthtech | None
    justification: str | None
    created_at: datetime
    updated_at: datetime

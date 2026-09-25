"""Schémas Pydantic pour `project_ai_act_classification` — service 3.3.12

(AI Act). `CategorieRisqueAiAct` reprend exactement les 5 valeurs de
`agents/ingestion/legal_text_structuring_service_ai_act.py::CategorieRisqueAIAct`
(voir docstring du modèle pour le raisonnement de cohérence)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

CategorieRisqueAiAct = Literal["interdit", "haut_risque", "risque_limite", "gouvernance_gpai", "minimal"]


class ProjectAiActClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    # None tant que le diagnostic n'a jamais ete lance (voir docstring modele).
    categorie_risque: CategorieRisqueAiAct | None
    justification: str | None
    created_at: datetime
    updated_at: datetime

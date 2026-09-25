"""Schémas Pydantic pour `project_certification_estimations` — service 3.3.11.

Aucun champ settable par le client (contrairement aux obligations, où
"statut" est coché manuellement) : une estimation n'est produite que par la
génération agent (voir secnumcloud_diagnostic_service.py), jamais éditée à la
main.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

TypeCertification = Literal["secnumcloud"]


class ProjectCertificationEstimationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type_certification: TypeCertification
    delai_mois_min: int
    delai_mois_max: int
    cout_estime_min: int
    cout_estime_max: int
    justification: str
    generated_at: datetime

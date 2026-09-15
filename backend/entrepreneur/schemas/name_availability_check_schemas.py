"""Schémas Pydantic pour `name_availability_checks` (service 1.1.2)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StatutDenomination = Literal["disponible", "pris"]
StatutMarque = Literal["disponible", "risque", "pris"]


class NameAvailabilityCheckCreate(BaseModel):
    """`project_id` vient du chemin de la route, pas du body — même convention
    que ProjectLegalProfileCreate."""

    nom_teste: str = Field(min_length=1, max_length=255)


class NameAvailabilityCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    nom_teste: str
    statut_denomination: StatutDenomination
    statut_marque: StatutMarque
    verifie_le: datetime

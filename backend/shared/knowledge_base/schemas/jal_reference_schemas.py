"""Schémas du dashboard de validation de `jal_reference` (service 1.1.5)."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JalReferenceValidationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom_journal: str
    type_support: str
    departements_couverts: list[str]
    lien_site: str | None
    source_url: str
    derniere_verification: date | None


class JalReferenceValidationAction(BaseModel):
    # Corrige l'heuristique papier/SPEL de la collecte si besoin.
    type_support: Literal["papier", "spel"] | None = None

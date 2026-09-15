"""Schemas Pydantic du dashboard de validation humaine des recommandations
d'assurance sectorielles (service 1.1.10) — meme convention que
`legal_texts_schemas.py` : requete/reponse separees des modeles SQLAlchemy
et des routes.
"""
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SectorInsuranceValidationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    secteur: str
    type_assurance: str
    a_base_legale: bool
    source_nom: str | None
    source_url: str | None
    texte_brut: str | None
    longueur_caracteres: int


class SectorInsuranceValidationAction(BaseModel):
    action: Literal["valider", "corriger"]

"""Schemas Pydantic du dashboard de validation humaine de
`administrative_guides` — meme convention que `legal_texts_schemas.py`."""
import uuid

from pydantic import BaseModel, ConfigDict


class AdministrativeGuideValidationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domaine: str
    source_nom: str
    source_url: str
    titre: str | None
    texte_brut: str
    longueur_caracteres: int

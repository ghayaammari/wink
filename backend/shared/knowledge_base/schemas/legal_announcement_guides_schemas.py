"""Schémas du dashboard de validation de `legal_announcement_guides` (service 1.1.5)."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LegalAnnouncementGuideValidationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_nom: str
    source_url: str
    titre: str
    sous_theme: str
    texte_brut: str

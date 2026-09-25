"""Schemas du formulaire pitch deck (service 6.6.2) — le profil saisi par

l'entrepreneur (ProjectPitchProfile). Le contenu genere (DeckContentModel)
n'a PAS de schema dedie ici : agents/pitch_deck_agent/deck_schema.py est
reutilise tel quel comme response_model par pitch_router.py -- dupliquer ses
11 classes de diapositives ici n'ajouterait aucune validation ni mapping
different, juste de la maintenance en double (voir "reste sobre").
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProjectPitchProfileRead(BaseModel):
    id: UUID
    project_id: UUID
    probleme: str | None = None
    solution: str | None = None
    marche: str | None = None
    modele_economique: str | None = None
    concurrence: str | None = None
    traction: str | None = None
    financements: str | None = None
    roadmap: str | None = None
    demande_investissement: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectPitchProfileUpdate(BaseModel):
    """Tous les champs optionnels (PATCH partiel) — meme convention que

    AiActDataProfileUpdate : seuls les champs presents dans la requete sont
    modifies (voir pitch_profile_service.py, model_dump(exclude_unset=True))."""

    probleme: str | None = None
    solution: str | None = None
    marche: str | None = None
    modele_economique: str | None = None
    concurrence: str | None = None
    traction: str | None = None
    financements: str | None = None
    roadmap: str | None = None
    demande_investissement: str | None = None

"""Schémas Pydantic pour `research_need_matches` — lecture uniquement côté
API : la génération passe toujours par l'agent (chercheur_matching_
orchestration_service.run_matching), jamais un payload envoyé par le
client. Seul `interesse` (marquage "intéressé") est modifiable côté client,
via un endpoint PATCH dédié (voir chercheur_matching_router.py), jamais en
réécrivant tout `matches`.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

NiveauPertinence = Literal["fort", "moyen", "faible"]


class ChercheurMatchRead(BaseModel):
    researcher_profile_id: UUID
    nom: str
    rang: int
    niveau_pertinence: NiveauPertinence
    explication: str
    interesse: bool = False


class ResearchNeedMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_need_id: UUID
    matches: list[ChercheurMatchRead]
    synthese: str
    created_at: datetime
    updated_at: datetime


class InteretUpdate(BaseModel):
    interesse: bool


class RecommandationInteressanteRead(BaseModel):
    """Une recommandation marquée "intéressé", enrichie du besoin dont elle

    vient — nécessaire pour la sous-section "Recommandations intéressantes"
    (sidebar), qui liste des recommandations à travers TOUS les besoins d'un
    projet, pas un seul (voir list_interesting_matches)."""

    need_id: UUID
    need_titre: str
    match: ChercheurMatchRead

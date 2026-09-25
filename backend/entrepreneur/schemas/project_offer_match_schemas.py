"""Schémas Pydantic pour `project_offer_matches` — lecture uniquement

côté API, même convention que investment_offer_match_schemas.py : la
génération passe toujours par l'agent (startup_offer_matching_
orchestration_service.run_matching), jamais un payload envoye par le
client. Seul `interesse` est modifiable, via un endpoint PATCH dedie.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

NiveauPertinence = Literal["fort", "moyen", "faible"]


class OfferMatchRead(BaseModel):
    offer_id: UUID
    rang: int
    niveau_pertinence: NiveauPertinence
    explication: str
    interesse: bool = False
    # Champs de la fiche vivante de l'offre (InvestmentOffer/InvestorProfile),
    # ajoutés en LECTURE seule par project_offer_match_service::
    # _enrichir_matches -- jamais écrits par l'agent ni stockés dans le
    # JSONB `matches` (même raisonnement que StartupMatchRead côté
    # investisseur). Absents -> None (ex. offre supprimée depuis).
    # `statut` permet de ne jamais laisser une offre fermée entre-temps
    # paraitre encore ouverte a l'entrepreneur.
    titre: str | None = None
    montant_propose: int | None = None
    secteurs_cibles: list[str] | None = None
    stades_cibles: list[str] | None = None
    investor_type: str | None = None
    statut: str | None = None


class ProjectOfferMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    matches: list[OfferMatchRead]
    synthese: str
    created_at: datetime
    updated_at: datetime


class InteretUpdate(BaseModel):
    interesse: bool

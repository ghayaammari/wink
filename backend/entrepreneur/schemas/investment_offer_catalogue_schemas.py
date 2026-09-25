"""Schéma de lecture du catalogue des offres d'investissement ouvertes,

visible par tout entrepreneur AVANT de lancer le matching (service 6.6.1,
"Feed de matching investisseurs" -- l'entrepreneur doit pouvoir parcourir
toutes les offres disponibles, pas seulement celles que l'agent recommande).
Fichier séparé de project_offer_match_schemas.py : responsabilité distincte
(catalogue brut, non scoré, non lié à un projet précis) vs résultat de
matching (scoré, lié à project_offer_matches).
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.investisseur.schemas.investor_schemas import InvestorType


class OfferCatalogueRead(BaseModel):
    id: UUID
    titre: str
    description: str
    montant_propose: int
    secteurs_cibles: list[str]
    stades_cibles: list[str]
    investor_type: InvestorType | None
    created_at: datetime

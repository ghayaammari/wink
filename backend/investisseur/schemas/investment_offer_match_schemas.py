"""Schémas Pydantic pour `investment_offer_matches` — lecture uniquement

côté API, même convention que research_need_match_schemas.py : la
génération passe toujours par l'agent (investisseur_matching_orchestration_
service.run_matching), jamais un payload envoyé par le client. Seul
`interesse` est modifiable, via un endpoint PATCH dédié.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

NiveauPertinence = Literal["fort", "moyen", "faible"]


class StartupMatchRead(BaseModel):
    project_id: UUID
    nom: str
    rang: int
    niveau_pertinence: NiveauPertinence
    explication: str
    interesse: bool = False
    # Champs de la fiche vivante du projet (Project/ProjectPublicProfile),
    # ajoutés en LECTURE seule par investment_offer_match_service::
    # _enrichir_matches -- jamais écrits par l'agent ni stockés dans le
    # JSONB `matches` (voir ce module). Absents -> None (ex. projet
    # supprimé depuis, ou vitrine publique jamais renseignée) : l'affichage
    # doit rester robuste à un champ manquant, pas planter dessus.
    secteur: str | None = None
    stade: str | None = None
    localisation: str | None = None
    value_proposition: str | None = None
    technologies: list[str] | None = None
    logo_url: str | None = None
    website_url: str | None = None


class InvestmentOfferMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investment_offer_id: UUID
    matches: list[StartupMatchRead]
    synthese: str
    created_at: datetime
    updated_at: datetime


class InteretUpdate(BaseModel):
    interesse: bool


class StartupInteressanteRead(BaseModel):
    """Une recommandation marquée "intéressé", enrichie de l'offre dont elle

    vient -- nécessaire pour la page transversale "Startups intéressantes"
    (toutes les offres de l'investisseur, pas une seule), même principe que
    RecommandationInteressanteRead côté chercheur."""

    offer_id: UUID
    offer_titre: str
    match: StartupMatchRead

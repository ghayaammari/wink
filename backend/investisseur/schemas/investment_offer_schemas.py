"""Schémas Pydantic pour `investment_offers` — CRUD simple, même convention

que research_need_schemas.py (matching côté chercheur). `investor_profile_id`
n'apparaît jamais dans les payloads d'entrée : toujours déduit de
l'utilisateur connecté (voir investment_offer_service.py).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

StatutOffre = Literal["ouvert", "ferme"]


class InvestmentOfferCreate(BaseModel):
    titre: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    montant_propose: int = Field(gt=0)
    secteurs_cibles: list[str] = Field(default_factory=list)
    stades_cibles: list[str] = Field(default_factory=list)


class InvestmentOfferRead(BaseModel):
    id: UUID
    investor_profile_id: UUID
    titre: str
    description: str
    montant_propose: int
    secteurs_cibles: list[str]
    stades_cibles: list[str]
    statut: StatutOffre
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvestmentOfferStatutUpdate(BaseModel):
    statut: StatutOffre

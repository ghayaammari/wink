"""Schémas Pydantic pour `research_needs` — service 7.7.1.

CRUD simple : tous les champs de saisie (type_besoin, titre, description)
sont settables par le client à la création, seul `statut` se modifie après
coup (fermeture d'un besoin), jamais nom/description réécrits une fois créés
-- si le besoin change vraiment, l'entrepreneur en dépose un nouveau plutôt
que d'éditer l'historique (cohérent avec le feed qui se recalcule par besoin,
pas question de faire dériver un feed déjà vu sous un texte modifié).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TypeBesoin = Literal["probleme", "expertise"]
StatutBesoin = Literal["ouvert", "ferme"]


class ResearchNeedCreate(BaseModel):
    type_besoin: TypeBesoin
    titre: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)


class ResearchNeedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type_besoin: TypeBesoin
    titre: str
    description: str
    statut: StatutBesoin
    created_at: datetime
    updated_at: datetime


class ResearchNeedStatutUpdate(BaseModel):
    statut: StatutBesoin

"""Schémas Pydantic — research_works.

Trois usages distincts : correction des champs extraits automatiquement par
le chercheur (service 0.0.2 — plus de saisie manuelle à la création, le VLM
remplit tout, le chercheur peut juste corriger après coup), lecture/
consultation (service 0.0.3), et validation d'un travail extrait
automatiquement (confirmer/rejeter après extraction HAL/OpenAlex).
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.chercheur.schemas.researcher_field_value_schemas import ResearcherFieldValueRead


class ResearchWorkUpdate(BaseModel):
    """Correction des champs extraits directement par le VLM (titre, résumé,
    auteurs, venue, doi, type de publication) — tous optionnels, seuls les
    champs fournis sont modifiés (voir model_dump(exclude_unset=True) côté
    service). Ne couvre jamais file_url ni source_type : un chercheur ne
    remplace pas le fichier déposé via ce endpoint, il redépose."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    abstract: str | None = None
    authors: list[str] | None = None
    venue: str | None = Field(default=None, max_length=255)
    doi: str | None = Field(default=None, max_length=100)
    publication_type: Literal["article", "communication", "these", "brevet", "rapport"] | None = None


class ResearchWorkValidationUpdate(BaseModel):
    """Confirmer ou rejeter un travail extrait automatiquement (pending_confirmation).
    Inchangé — toujours utilisé pour les travaux extrait_hal_openalex, pas
    concerné par le changement de flux du dépôt manuel."""

    validation_status: Literal["confirmed", "rejected"]
    visibility: Literal["public_profile", "private_matching_only"] | None = None


class ResearchWorkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    researcher_profile_id: uuid.UUID
    title: str
    abstract: str | None
    authors: list | None
    venue: str | None
    doi: str | None
    external_url: str | None
    publication_type: str | None
    source_type: Literal["extrait_hal_openalex", "depot_manuel"]
    file_url: str | None
    validation_status: Literal["pending_confirmation", "confirmed", "rejected"]
    visibility: Literal["public_profile", "private_matching_only"]
    created_at: datetime
    updated_at: datetime
    generated_field_values: list[ResearcherFieldValueRead] = []
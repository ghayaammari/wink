"""Schémas Pydantic — researcher_profiles.

`ResearcherOnboardingRequest` couvre les étapes 3-5 du PDF onboarding, envoyées
en un seul appel POST /chercheur/onboarding (décision actée avec l'utilisateur).
`extraction_preference` n'est jamais stocké en base — utilisé uniquement par
le service pour décider s'il faut déclencher l'extraction HAL/OpenAlex.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.chercheur.schemas.researcher_field_value_schemas import ResearcherFieldValueRead


class ResearcherOnboardingRequest(BaseModel):
    affiliation: str = Field(..., min_length=1, max_length=255)
    extraction_preference: Literal["extraire", "deposer", "les_deux"]
    # Obligatoire seulement si extraction_preference != "deposer" — validé côté service,
    # pas ici, car la règle dépend d'un autre champ du même schéma.
    orcid_id: str | None = Field(default=None, max_length=19)
    # Optionnel — nécessaire surtout pour "déposer" (jamais d'extraction donc jamais
    # de domaines détectés automatiquement sans ça), mais laissé ouvert quel que soit
    # le choix : rien n'empêche un chercheur de préciser ses domaines dès l'onboarding
    # même s'il attend aussi une extraction. Multi-valeur, cohérent avec le mécanisme
    # research_field_values déjà en place (pas de valeur unique à superposer).
    research_domains: list[str] = Field(default_factory=list)


class ResearcherProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    orcid_id: str | None
    affiliation: str | None
    research_domains: list[str]
    sync_status: Literal["not_started", "queued", "in_progress", "completed", "failed"]
    last_synced_at: datetime | None
    expertise_summary: str | None
    research_work_summary: str | None
    profile_completion: Literal["incomplet", "complet"]
    created_at: datetime
    updated_at: datetime
    # Attaché en attribut Python par researcher_profile_service.get_profile_with_pending_fields
    # (pas une colonne réelle sur researcher_profiles) — jamais présent sur un objet
    # ResearcherProfile "brut" venant juste de la DB, d'où le défaut [] pour ne pas
    # planter la validation si ce schéma sert ailleurs sans cet attribut attaché.
    generated_field_values: list[ResearcherFieldValueRead] = Field(default_factory=list)


class ResearcherProfileUpdateRequest(BaseModel):
    orcid_id: str | None = None
    affiliation: str | None = None
    research_domains: list[str] | None = None
    expertise_summary: str | None = None
    research_work_summary: str | None = None
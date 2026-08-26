"""Schémas Pydantic pour `project_legal_profiles` — identité légale du projet."""
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectLegalProfileBase(BaseModel):
    is_registered: bool = False
    legal_name: str | None = Field(default=None, max_length=255)
    legal_form: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    # SIREN/SIRET : longueur fixe en chiffres — validés ici pour éviter un aller-retour DB inutile.
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    siret: str | None = Field(default=None, pattern=r"^\d{14}$")
    vat_number: str | None = Field(default=None, max_length=40)
    naf_code: str | None = Field(default=None, max_length=10)
    registration_date: date | None = None
    registered_address: dict[str, Any] | None = None
    legal_representative: dict[str, Any] | None = None


class ProjectLegalProfileCreate(ProjectLegalProfileBase):
    """`project_id` vient du chemin de la route (`/projects/{project_id}/legal-profile`), pas du body."""


class ProjectLegalProfileUpdate(BaseModel):
    is_registered: bool | None = None
    legal_name: str | None = Field(default=None, max_length=255)
    legal_form: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    siret: str | None = Field(default=None, pattern=r"^\d{14}$")
    vat_number: str | None = Field(default=None, max_length=40)
    naf_code: str | None = Field(default=None, max_length=10)
    registration_date: date | None = None
    registered_address: dict[str, Any] | None = None
    legal_representative: dict[str, Any] | None = None
    # verification_status volontairement absent : c'est le résultat d'une vérification
    # (service futur EPIC-01), pas un champ que l'entrepreneur édite lui-même.


class ProjectLegalProfileRead(ProjectLegalProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    # str et non Literal : le schéma de données ne pose pas de CHECK sur cette colonne
    # (contrairement aux autres champs à choix). À restreindre en Literal dès que les
    # valeurs possibles (ex: unverified/pending/verified/rejected) seront actées.
    verification_status: str
    created_at: datetime
    updated_at: datetime

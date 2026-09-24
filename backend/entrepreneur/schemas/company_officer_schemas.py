"""Schémas Pydantic pour `company_officers` — mandats de dirigeants désignés dans
les statuts SAS (art. 39-41). Design validé avec l'utilisateur (22/09/2026,
catégorie B3 de l'inventaire des 210 variables — voir modèle company_officer.py)."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Même liste que le CHECK en base (`ck_company_officers_role`). 'mandataire' :
# associé chargé des actes de la société en formation (art. 44 + Annexe III
# de la clôture) -- absent de ces schémas jusqu'au lot 5 (24/09/2026).
RoleDirigeant = Literal["president", "directeur_general", "membre_comite", "mandataire"]


class CompanyOfficerBase(BaseModel):
    # Mandat exercé (art. 39 Président, 40 Directeur Général, 41 membres du
    # comité, 44 mandataire).
    role: RoleDirigeant
    # Anti-redondance : si le dirigeant est déjà associé, on ne stocke que la FK.
    associate_id: UUID | None = None
    type_personne: Literal["personne_physique", "personne_morale"] = "personne_physique"
    duree_fonctions: str | None = Field(default=None, max_length=120)
    # Identité d'un dirigeant PERSONNE PHYSIQUE non associé (colonne ajoutée par
    # la migration acb040c7128a, jamais exposée avant le lot 5).
    nom_complet: str | None = Field(default=None, max_length=255)
    # Champs personne morale dirigeante (utilisés si type_personne='personne_morale'
    # et associate_id est NULL — sinon l'identité vit dans project_associates).
    denomination_sociale: str | None = Field(default=None, max_length=255)
    forme_juridique: str | None = Field(default=None, max_length=120)
    capital_social: Decimal | None = Field(default=None, ge=Decimal("0"))
    siege_social: str | None = None
    lieu_immatriculation: str | None = Field(default=None, max_length=120)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    representant_nom: str | None = Field(default=None, max_length=120)
    representant_prenom: str | None = Field(default=None, max_length=120)
    adresse: str | None = None


class CompanyOfficerCreate(CompanyOfficerBase):
    """`project_id` vient du chemin de la route (`/projects/{project_id}/officers`).
    Règles d'identité, d'unicité du rôle et d'appartenance de l'associé :
    vérifiées dans company_officer_service (état FINAL, après fusion pour un
    PATCH), pas ici."""


class CompanyOfficerUpdate(BaseModel):
    role: RoleDirigeant | None = None
    associate_id: UUID | None = None
    type_personne: Literal["personne_physique", "personne_morale"] | None = None
    duree_fonctions: str | None = Field(default=None, max_length=120)
    nom_complet: str | None = Field(default=None, max_length=255)
    denomination_sociale: str | None = Field(default=None, max_length=255)
    forme_juridique: str | None = Field(default=None, max_length=120)
    capital_social: Decimal | None = Field(default=None, ge=Decimal("0"))
    siege_social: str | None = None
    lieu_immatriculation: str | None = Field(default=None, max_length=120)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    representant_nom: str | None = Field(default=None, max_length=120)
    representant_prenom: str | None = Field(default=None, max_length=120)
    adresse: str | None = None


class CompanyOfficerRead(CompanyOfficerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
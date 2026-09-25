"""Schémas Pydantic pour `project_legal_profiles` — identité légale du projet."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectLegalProfileBase(BaseModel):
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
    # Le représentant légal est un associé (FK vers project_associates) — voir modèle.
    # Non obligatoire ici : sa désignation intervient après rédaction des statuts (1.1.4),
    # mais une société déjà immatriculée doit l'avoir renseigné (validation applicative).
    legal_representative_associate_id: UUID | None = None
    objet_social: str | None = None
    duree_societe: int | None = Field(default=None, ge=1, le=99)
    date_signature_statuts: date | None = None
    # B2 (service 1.1.4 statuts SAS) — faits juridiques, voir modèle/migration f5a7c9e1d3b2.
    raison_d_etre: str | None = None
    objectifs_ess: str | None = None
    sigle: str | None = Field(default=None, max_length=120)
    lieu_signature_statuts: str | None = Field(default=None, max_length=255)
    # Lot 1 (24/09/2026, service 1.1.4) — capital du PROJET, colonnes déjà en
    # base (migration 507ed2995d84) mais jamais exposées : lues par les statuts
    # (Art. 6/7, apports au prorata) et le Préambule du pacte. Cohérence
    # nombre_actions × valeur_nominale = capital_social contrôlée dans
    # project_service.update_legal_profile (après fusion avec l'existant).
    capital_social: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=14, decimal_places=2)
    nombre_actions: int | None = Field(default=None, ge=1)
    valeur_nominale: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=10, decimal_places=2)
    lieu_immatriculation: str | None = Field(default=None, max_length=120)


class ProjectLegalProfileCreate(ProjectLegalProfileBase):
    """`project_id` vient du chemin de la route (`/projects/{project_id}/legal-profile`), pas du body."""


class ProjectLegalProfileUpdate(BaseModel):
    legal_name: str | None = Field(default=None, max_length=255)
    legal_form: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    siret: str | None = Field(default=None, pattern=r"^\d{14}$")
    vat_number: str | None = Field(default=None, max_length=40)
    naf_code: str | None = Field(default=None, max_length=10)
    registration_date: date | None = None
    registered_address: dict[str, Any] | None = None
    legal_representative_associate_id: UUID | None = None
    objet_social: str | None = None
    duree_societe: int | None = Field(default=None, ge=1, le=99)
    date_signature_statuts: date | None = None
    # B2 (service 1.1.4 statuts SAS) — faits juridiques, voir modèle/migration f5a7c9e1d3b2.
    raison_d_etre: str | None = None
    objectifs_ess: str | None = None
    sigle: str | None = Field(default=None, max_length=120)
    lieu_signature_statuts: str | None = Field(default=None, max_length=255)
    # Lot 1 (24/09/2026, service 1.1.4) — capital du PROJET, colonnes déjà en
    # base (migration 507ed2995d84) mais jamais exposées : lues par les statuts
    # (Art. 6/7, apports au prorata) et le Préambule du pacte. Cohérence
    # nombre_actions × valeur_nominale = capital_social contrôlée dans
    # project_service.update_legal_profile (après fusion avec l'existant).
    capital_social: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=14, decimal_places=2)
    nombre_actions: int | None = Field(default=None, ge=1)
    valeur_nominale: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=10, decimal_places=2)
    lieu_immatriculation: str | None = Field(default=None, max_length=120)
    # Volontairement absents de ce PATCH générique — tous écrits par des mécanismes
    # dédiés, jamais par une édition libre de l'entrepreneur (voir "Schemas grp 4") :
    # - les 3 statuts de vérification : résultat d'un appel API (Parcours B) ou d'un
    #   job périodique (Parcours A), jamais une valeur que l'entrepreneur choisit
    # - numero_suivi_formalite : écrit une seule fois au dépôt Guichet Unique (e13)
    # - kbis_document_id : upload manuel, mais via un endpoint dédié à créer
    #   (même pattern que roadmap_service.attach_proof), pas ce PATCH générique


class ProjectLegalProfileRead(ProjectLegalProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    kbis_document_id: UUID | None
    # str et non Literal : le schéma de données pose un CHECK en base (voir modèle),
    # mais rien n'empêche une future 4e valeur sans toucher ce schéma de lecture.
    denomination_verification_status: str
    immatriculation_verification_status: str
    kbis_verification_status: str
    numero_suivi_formalite: str | None
    created_at: datetime
    updated_at: datetime

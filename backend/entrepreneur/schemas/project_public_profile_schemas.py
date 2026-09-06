"""Schémas Pydantic pour `project_public_profiles` — vitrine publique du projet."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.entrepreneur.schemas.project_field_value_schemas import FieldValueResolution

# Reflète le CheckConstraint ajouté sur project_public_profiles (voir migration
# 82a64157b35d) — avant ça, ces 2 colonnes n'avaient aucune valeur imposée ni en
# base ni côté schéma (voir schema-i0-entrepreneur.md, désormais obsolète sur ce
# point précis).
ProjectVisibility = Literal["private", "public", "investors_only"]


class ProjectPublicProfileBase(BaseModel):
    public_name: str | None = Field(default=None, max_length=255)
    public_summary: str | None = None
    sector: str | None = Field(default=None, max_length=120)
    technologies: list[str] = Field(default_factory=list)
    website_url: str | None = None
    # URL Cloudinary directe (pas de FK) — écrite par le service d'upload de logo, pas saisie à la main.
    logo_url: str | None = None
    funding_visibility: ProjectVisibility = "private"
    compliance_visibility: ProjectVisibility = "private"


class ProjectPublicProfileCreate(ProjectPublicProfileBase):
    """`project_id` vient du chemin de la route, pas du body."""


class ProjectPublicProfileUpdate(BaseModel):
    public_name: str | None = Field(default=None, max_length=255)
    public_summary: str | None = None
    sector: str | None = Field(default=None, max_length=120)
    technologies: list[str] | None = None
    website_url: str | None = None
    logo_url: str | None = None
    funding_visibility: ProjectVisibility | None = None
    compliance_visibility: ProjectVisibility | None = None
    # published_at absent : ce n'est pas un champ éditable, c'est l'horodatage d'une action
    # "publier" côté service (EPIC-06 plus tard), pas une donnée saisie par l'entrepreneur.

    # Résolutions explicites des champs extraits affichés sur cet écran (confirmation
    # globale — voir DECISIONS). Voir ProjectUpdate.resolved_field_values pour le détail.
    resolved_field_values: list[FieldValueResolution] | None = None


class ProjectPublicProfileRead(ProjectPublicProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    published_at: datetime | None
    updated_at: datetime

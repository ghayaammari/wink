"""Schémas Pydantic pour `project_public_profiles` — vitrine publique du projet."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.entrepreneur.schemas.project_field_value_schemas import FieldValueResolution


class ProjectPublicProfileBase(BaseModel):
    public_name: str | None = Field(default=None, max_length=255)
    public_summary: str | None = None
    sector: str | None = Field(default=None, max_length=120)
    technologies: list[str] = Field(default_factory=list)
    website_url: str | None = None
    # URL Cloudinary directe (pas de FK) — écrite par le service d'upload de logo, pas saisie à la main.
    logo_url: str | None = None
    # str et non Literal : ni funding_visibility ni compliance_visibility n'ont de CHECK
    # documenté dans le schéma de données (contrairement à project_type/stage/... sur `projects`).
    # À restreindre en Literal["private", "public", ...] dès que les valeurs seront actées.
    funding_visibility: str = "private"
    compliance_visibility: str = "private"


class ProjectPublicProfileCreate(ProjectPublicProfileBase):
    """`project_id` vient du chemin de la route, pas du body."""


class ProjectPublicProfileUpdate(BaseModel):
    public_name: str | None = Field(default=None, max_length=255)
    public_summary: str | None = None
    sector: str | None = Field(default=None, max_length=120)
    technologies: list[str] | None = None
    website_url: str | None = None
    logo_url: str | None = None
    funding_visibility: str | None = None
    compliance_visibility: str | None = None
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

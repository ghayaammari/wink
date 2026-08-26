"""Schémas Pydantic pour `projects` — l'idée ou la startup présentée par l'entrepreneur."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.entrepreneur.schemas.project_field_value_schemas import FieldValueResolution

ProjectType = Literal["not_created", "created"]
ProjectStage = Literal["ideation", "pre_seed", "seed", "serie_a"]
ProjectSourceType = Literal["texte_libre", "document_importe"]
ProjectProfileCompletion = Literal["incomplet", "complet"]


class ProjectCreate(BaseModel):
    """Entrée du service 0.0.2, écran 2 — uniquement project_type/stage.

    description et source_type ne sont pas demandés ici : le questionnaire les
    répond à l'écran 4, pas à la création (voir Project.description dans
    entrepreneur/models/project.py pour le détail de cet état transitoire).
    """

    project_type: ProjectType
    stage: ProjectStage


class ProjectUpdate(BaseModel):
    """Toutes les colonnes sont optionnelles — PATCH partiel (écrans 4 à 8, service 0.0.3/0.0.4).

    source_type volontairement absent : jamais envoyé par le client dans ce
    parcours manuel — le service le fixe lui-même à "texte_libre" dès que
    `description` est répondue pour la première fois (voir project_service.py).
    """

    project_type: ProjectType | None = None
    stage: ProjectStage | None = None
    description: str | None = Field(default=None, min_length=1)
    nombre_cofondateurs: int | None = Field(default=None, ge=0)
    intention_levee_fonds: bool | None = None
    localisation: str | None = Field(default=None, max_length=120)
    sector: str | None = Field(default=None, max_length=120)
    subsectors: list[str] | None = None
    customer_segments: list[str] | None = None
    target_users: list[str] | None = None
    technologies: list[str] | None = None
    value_proposition: str | None = None
    # imported_document_id absent : hors périmètre du parcours manuel (v0 sans doc).

    # Résolutions explicites des champs extraits affichés sur cet écran (confirmation
    # globale — voir DECISIONS) : envoyées dans le MÊME payload que le PATCH plutôt qu'en
    # appels séparés. Jamais déduites par diff de valeur côté backend, voir FieldValueResolution.
    resolved_field_values: list[FieldValueResolution] | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entrepreneur_profile_id: UUID
    project_type: ProjectType
    stage: ProjectStage
    description: str | None
    source_type: ProjectSourceType | None
    imported_document_id: UUID | None
    nombre_cofondateurs: int | None
    intention_levee_fonds: bool | None
    localisation: str | None
    sector: str | None
    subsectors: list[str]
    customer_segments: list[str]
    target_users: list[str]
    technologies: list[str]
    value_proposition: str | None
    # Statut grossier stocké en base (CHECK IN incomplet/complet) — dérivé de
    # completion_percentage, recalculé et persisté à chaque écriture.
    project_profile_completion: ProjectProfileCompletion
    # Champ calculé, jamais stocké en base (la colonne DB ne peut contenir qu'un
    # str incomplet/complet, pas un nombre) — attaché dynamiquement à l'objet
    # ORM par project_service avant sérialisation. Voir _compute_completion.
    completion_percentage: int
    created_at: datetime
    updated_at: datetime

"""Schémas Pydantic pour `project_field_values` — traçabilité des champs extraits automatiquement."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ExtractionSource = Literal["extrait_automatique", "saisi_par_utilisateur"]
ValidationStatus = Literal["en_attente", "confirme", "corrige"]


class ProjectFieldValueCreate(BaseModel):
    """Schéma interne au pipeline d'extraction — pas une route publique.

    Écrit par le service d'ingestion de document (service 0.0.2) après extraction,
    ou par la saisie manuelle initiale — jamais un POST direct du client.
    """

    project_id: UUID
    field_name: str = Field(max_length=100)
    field_value: str | None = None
    extraction_source: ExtractionSource
    validation_status: ValidationStatus = "en_attente"


class ProjectFieldValueUpdate(BaseModel):
    """Ce que l'entrepreneur envoie pour confirmer ou corriger un champ extrait (service 0.0.2)."""

    field_value: str | None = None
    validation_status: ValidationStatus


class ProjectFieldValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    field_name: str
    field_value: str | None
    extraction_source: ExtractionSource
    validation_status: ValidationStatus
    created_at: datetime
    updated_at: datetime


ResolutionAction = Literal["confirme", "corrige", "ignore"]


class FieldValueResolution(BaseModel):
    """Une résolution explicite envoyée par le frontend pour un champ extrait, dans le

    même payload que le PATCH `projects`/`project_public_profiles` de l'écran
    ("confirmation globale" — voir DECISIONS). Jamais déduite par comparaison de
    valeurs côté backend : le frontend sait déjà, au moment de l'affichage, si
    l'utilisateur a touché ou ignoré ce champ — pas la peine de deviner ici.
    """

    id: UUID
    action: ResolutionAction

"""Schémas Pydantic pour `documents` — métadonnées d'un fichier importé (le binaire reste sur Cloudinary)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

DocumentType = Literal["entrepreneur_idea", "other"]
DocumentVisibility = Literal["private", "project_members"]
DocumentProcessingStatus = Literal["uploaded", "queued", "processing", "ready", "failed"]


class DocumentCreate(BaseModel):
    """Crée l'entrée `documents` associée à un upload — `owner_user_id` vient du contexte auth."""

    document_type: DocumentType
    visibility: DocumentVisibility = "private"
    project_id: UUID | None = None


class DocumentUpdate(BaseModel):
    """Seule la visibilité et le rattachement à un projet sont éditables après coup."""

    visibility: DocumentVisibility | None = None
    project_id: UUID | None = None
    # processing_status et current_version_id volontairement absents : pilotés par le
    # pipeline d'ingestion/upload (service 0.0.2), jamais écrits directement par le client.


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_user_id: UUID
    project_id: UUID | None
    document_type: DocumentType
    visibility: DocumentVisibility
    processing_status: DocumentProcessingStatus
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime

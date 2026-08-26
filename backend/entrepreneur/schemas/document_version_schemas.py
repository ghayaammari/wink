"""Schémas Pydantic pour `document_versions` — version immuable d'un fichier (référence Cloudinary)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentVersionCreate(BaseModel):
    """Schéma interne au service d'upload — jamais rempli à la main par le client.

    Construit par `document_service` une fois la réponse Cloudinary reçue (pas de route
    qui accepte ce body tel quel : le client envoie un fichier multipart, pas ce JSON).
    """

    document_id: UUID
    version_number: int = Field(ge=1)
    original_filename: str = Field(max_length=500)
    cloudinary_public_id: str = Field(max_length=500)
    secure_url: str
    mime_type: str = Field(max_length=150)
    size_bytes: int = Field(ge=0)
    extracted_text_location: str | None = None


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    original_filename: str
    cloudinary_public_id: str
    secure_url: str
    mime_type: str
    size_bytes: int
    extracted_text_location: str | None
    created_at: datetime

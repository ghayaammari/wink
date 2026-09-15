"""Routes du service 1.1.17 — coffre-fort documentaire.

GET /projects/{id}/documents : liste tous les documents du projet, enrichis
de leur dernière version (nom de fichier, taille).

GET /projects/{id}/documents/{document_id}/download : télécharge la version
COURANTE d'un document. GET .../versions liste tout l'historique de ses
versions, et .../versions/{version_id}/download en télécharge une précise.
Toutes ces routes passent par le backend (pas une URL Cloudinary directe) —
voir la docstring de document_vault_service.get_document_download() pour
pourquoi.

Fichier distinct de document_router.py (scopé au service 0.0.2, upload +
extraction) : responsabilité différente — voir Wink_architecture_fichiers.md.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.document_vault_schemas import DocumentVaultItemRead, DocumentVersionRead
from backend.entrepreneur.services import document_vault_service
from backend.entrepreneur.services.document_vault_service import (
    DocumentDownloadError,
    DocumentNotFoundError,
    DocumentVaultError,
)
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-document-vault"])


def _handle_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_document_error/_handle_error dans les autres
    routers entrepreneur — un seul point de mapping erreur métier -> code HTTP.
    """
    if isinstance(exc, (ProjectNotFoundError, DocumentNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, DocumentDownloadError):
        # 502 : l'échec vient de Cloudinary (dépendance externe), pas d'une
        # requête invalide du client — distinct des 400 génériques ci-dessous.
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _file_response(content: bytes, filename: str, mime_type: str) -> Response:
    """Factorisé entre download_document() et download_document_version() : même
    construction de header Content-Disposition, seule la source du contenu change.
    """
    # Guillemets dans le nom de fichier original : casseraient la syntaxe de
    # l'en-tête Content-Disposition si repris tel quel.
    safe_filename = filename.replace('"', "'")
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.get("/{project_id}/documents", response_model=list[DocumentVaultItemRead])
def list_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentVaultItemRead]:
    try:
        return document_vault_service.list_project_documents(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/documents/{document_id}/download")
def download_document(
    project_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        content, filename, mime_type = document_vault_service.get_document_download(
            db, current_user, project_id, document_id
        )
    except (ProjectError, DocumentVaultError) as exc:
        raise _handle_error(exc)

    return _file_response(content, filename, mime_type)


@router.get("/{project_id}/documents/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_versions(
    project_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentVersionRead]:
    try:
        return document_vault_service.list_document_versions(db, current_user, project_id, document_id)
    except (ProjectError, DocumentVaultError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/documents/{document_id}/versions/{version_id}/download")
def download_document_version(
    project_id: UUID,
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        content, filename, mime_type = document_vault_service.get_document_version_download(
            db, current_user, project_id, document_id, version_id
        )
    except (ProjectError, DocumentVaultError) as exc:
        raise _handle_error(exc)

    return _file_response(content, filename, mime_type)

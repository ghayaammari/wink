"""Routes de l'import de document — upload PDF, extraction automatique, et
résolution (confirmer/corriger/ignorer) des champs extraits. Service 0.0.2,
volet "import de document".

POST /projects/{id}/upload-document, GET /projects/{id}/field-values,
PATCH /projects/{id}/field-values/{field_value_id},
DELETE /projects/{id}/field-values/{field_value_id}.

Fichier distinct de project_router.py : responsabilité différente (documents/
field_values, pas le CRUD du projet lui-même) — voir Wink_architecture_fichiers.md.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.project_field_value_schemas import ProjectFieldValueRead, ProjectFieldValueUpdate
from backend.entrepreneur.services import document_service
from backend.entrepreneur.services.document_service import DocumentNotFoundError, DocumentServiceError
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-documents"])


def _handle_document_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_project_error dans project_router.py — un seul

    point de mapping erreur métier -> code HTTP.
    """
    if isinstance(exc, (ProjectNotFoundError, DocumentNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{project_id}/upload-document",
    response_model=list[ProjectFieldValueRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectFieldValueRead]:
    file_bytes = await file.read()
    try:
        return document_service.upload_and_extract(
            db, current_user, project_id, file_bytes, file.filename, file.content_type
        )
    except (ProjectError, DocumentServiceError) as exc:
        raise _handle_document_error(exc)


@router.get("/{project_id}/field-values", response_model=list[ProjectFieldValueRead])
def list_field_values(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectFieldValueRead]:
    try:
        return document_service.list_field_values(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_document_error(exc)


@router.patch("/{project_id}/field-values/{field_value_id}", response_model=ProjectFieldValueRead)
def resolve_field_value(
    project_id: UUID,
    field_value_id: UUID,
    body: ProjectFieldValueUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFieldValueRead:
    try:
        return document_service.resolve_field_value(db, current_user, project_id, field_value_id, body)
    except (ProjectError, DocumentServiceError) as exc:
        raise _handle_document_error(exc)


@router.delete("/{project_id}/field-values/{field_value_id}", status_code=status.HTTP_204_NO_CONTENT)
def ignore_field_value(
    project_id: UUID,
    field_value_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        document_service.ignore_field_value(db, current_user, project_id, field_value_id)
    except (ProjectError, DocumentServiceError) as exc:
        raise _handle_document_error(exc)

"""Routes du "Plan d'action pré-création" — suivi de progression + dépôt de
preuve sur la roadmap `roadmap_nodes`/`startup_roadmap_items`. Service
formalisé dans "Wink — Plan d'action pré-création : spécification" (V1).

GET /projects/{id}/roadmap, PATCH /projects/{id}/roadmap/{node_id},
POST /projects/{id}/roadmap/{node_id}/proof.

Fichier distinct de project_router.py / document_router.py : responsabilité
différente (roadmap, pas le CRUD du projet ni l'import de document
d'onboarding) — voir Wink_architecture_fichiers.md.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.roadmap_schemas import RoadmapItemRead, RoadmapItemUpdate
from backend.entrepreneur.services import roadmap_service
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.entrepreneur.services.roadmap_service import RoadmapItemNotFoundError, RoadmapServiceError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-roadmap"])


def _handle_roadmap_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_project_error/_handle_document_error — un

    seul point de mapping erreur métier -> code HTTP.
    """
    if isinstance(exc, (ProjectNotFoundError, RoadmapItemNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/roadmap", response_model=list[RoadmapItemRead])
def get_roadmap(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RoadmapItemRead]:
    try:
        return roadmap_service.list_roadmap(db, current_user, project_id)
    except (ProjectError, RoadmapServiceError) as exc:
        raise _handle_roadmap_error(exc)


@router.patch("/{project_id}/roadmap/{node_id}", response_model=RoadmapItemRead)
def update_roadmap_item(
    project_id: UUID,
    node_id: str,
    body: RoadmapItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoadmapItemRead:
    try:
        return roadmap_service.update_status(db, current_user, project_id, node_id, body.statut)
    except (ProjectError, RoadmapServiceError) as exc:
        raise _handle_roadmap_error(exc)


@router.post(
    "/{project_id}/roadmap/{node_id}/proof",
    response_model=RoadmapItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_roadmap_proof(
    project_id: UUID,
    node_id: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoadmapItemRead:
    file_bytes = await file.read()
    try:
        return roadmap_service.attach_proof(
            db, current_user, project_id, node_id, file_bytes, file.filename, file.content_type
        )
    except (ProjectError, RoadmapServiceError) as exc:
        raise _handle_roadmap_error(exc)

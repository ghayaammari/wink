"""Routes de `research_needs` — service 7.7.1. Fichier distinct des routes

entrepreneur (`project_router.py` etc.) : vit dans `backend/matching/`,
cross-acteurs, même règle que le modèle (voir research_need.py).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.matching.schemas.research_need_schemas import ResearchNeedCreate, ResearchNeedRead, ResearchNeedStatutUpdate
from backend.matching.services.research_need_service import ResearchNeedNotFoundError, create_need, list_needs, update_statut
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["matching-research-needs"])


def _handle_research_need_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ProjectNotFoundError, ResearchNeedNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/matching/research-needs", response_model=ResearchNeedRead)
def creer_besoin_recherche(
    project_id: UUID,
    body: ResearchNeedCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchNeedRead:
    try:
        return create_need(db, current_user, project_id, body.type_besoin, body.titre, body.description)
    except ProjectError as exc:
        raise _handle_research_need_error(exc)


@router.get("/{project_id}/matching/research-needs", response_model=list[ResearchNeedRead])
def lister_besoins_recherche(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResearchNeedRead]:
    try:
        return list_needs(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_research_need_error(exc)


@router.patch("/{project_id}/matching/research-needs/{need_id}", response_model=ResearchNeedRead)
def fermer_besoin_recherche(
    project_id: UUID,
    need_id: UUID,
    body: ResearchNeedStatutUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchNeedRead:
    try:
        return update_statut(db, current_user, project_id, need_id, body.statut)
    except (ProjectError, ResearchNeedNotFoundError) as exc:
        raise _handle_research_need_error(exc)

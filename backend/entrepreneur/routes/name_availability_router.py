"""Routes du service 1.1.2 — vérificateur croisé de disponibilité du nom.

POST /projects/{id}/name-availability-checks (lance une vérification),
GET /projects/{id}/name-availability-checks (historique des noms déjà testés).

Fichier distinct de project_router.py/roadmap_router.py : responsabilité
différente (Groupe 4, service indépendant du copilot) — voir
Wink_architecture_fichiers.md.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.name_availability_check_schemas import (
    NameAvailabilityCheckCreate,
    NameAvailabilityCheckRead,
)
from backend.entrepreneur.services import name_availability_service
from backend.entrepreneur.services.name_availability_service import (
    NameAvailabilityServiceError,
    NameAvailabilityUpstreamError,
)
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-name-availability"])


def _handle_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_project_error/_handle_roadmap_error — un seul
    point de mapping erreur métier -> code HTTP.
    """
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, NameAvailabilityUpstreamError):
        # 503, pas 400 : l'échec vient d'une API externe (Recherche d'Entreprises
        # ou INPI), pas d'une erreur de saisie de l'utilisateur.
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{project_id}/name-availability-checks",
    response_model=NameAvailabilityCheckRead,
    status_code=status.HTTP_201_CREATED,
)
def create_name_availability_check(
    project_id: UUID,
    body: NameAvailabilityCheckCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NameAvailabilityCheckRead:
    try:
        return name_availability_service.check_name_availability(db, current_user, project_id, body.nom_teste)
    except (ProjectError, NameAvailabilityServiceError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/name-availability-checks", response_model=list[NameAvailabilityCheckRead])
def get_name_availability_checks(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NameAvailabilityCheckRead]:
    try:
        return name_availability_service.list_name_availability_checks(db, current_user, project_id)
    except (ProjectError, NameAvailabilityServiceError) as exc:
        raise _handle_error(exc)

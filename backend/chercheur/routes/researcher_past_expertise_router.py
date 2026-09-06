"""Routes des expertises passées — service optionnel de profil, accessible
depuis le profil à tout moment, jamais demandé à l'onboarding (voir
researcher_past_expertise.py).

POST /chercheur/expertises, GET /chercheur/expertises, PATCH
/chercheur/expertises/{expertise_id}.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.chercheur.schemas.researcher_past_expertise_schemas import (
    PastExpertiseCreate,
    PastExpertiseRead,
    PastExpertiseUpdate,
)
from backend.chercheur.services import researcher_past_expertise_service
from backend.chercheur.services.researcher_past_expertise_service import (
    PastExpertiseForbiddenError,
    PastExpertiseNotFoundError,
)
from backend.chercheur.services.researcher_profile_service import ResearcherProfileNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/chercheur/expertises", tags=["chercheur-expertises"])


def _require_chercheur_role(current_user: User) -> None:
    if current_user.role != "chercheur":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux comptes chercheur.")


def _handle_expertise_error(exc: Exception) -> HTTPException:
    """Un seul point de mapping erreur métier -> code HTTP, même convention
    que _handle_work_error côté research_work_router."""
    if isinstance(exc, (ResearcherProfileNotFoundError, PastExpertiseNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PastExpertiseForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=PastExpertiseRead, status_code=status.HTTP_201_CREATED)
def create_expertise(
    body: PastExpertiseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PastExpertiseRead:
    _require_chercheur_role(current_user)
    try:
        return researcher_past_expertise_service.create_for_user(db, current_user, body)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_expertise_error(exc)


@router.get("", response_model=list[PastExpertiseRead])
def list_expertises(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PastExpertiseRead]:
    _require_chercheur_role(current_user)
    try:
        return researcher_past_expertise_service.list_for_user(db, current_user)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_expertise_error(exc)


@router.patch("/{expertise_id}", response_model=PastExpertiseRead)
def update_expertise(
    expertise_id: UUID,
    body: PastExpertiseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PastExpertiseRead:
    _require_chercheur_role(current_user)
    try:
        return researcher_past_expertise_service.update_for_user(db, current_user, expertise_id, body)
    except (ResearcherProfileNotFoundError, PastExpertiseNotFoundError, PastExpertiseForbiddenError) as exc:
        raise _handle_expertise_error(exc)
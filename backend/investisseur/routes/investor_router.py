"""Routes du profil investisseur — services 0.0.2 à 0.0.4, parcours
linéaire (une seule table, pas de branchement).

POST /investisseur/onboarding, GET /investisseur/profile,
PATCH /investisseur/profile.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.investisseur.schemas.investor_schemas import (
    InvestorOnboardingRequest,
    InvestorProfileRead,
    InvestorProfileUpdate,
)
from backend.investisseur.services import investor_service
from backend.investisseur.services.investor_service import InvestorProfileNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/investisseur", tags=["investisseur-profile"])


def _require_investisseur_role(current_user: User) -> None:
    if current_user.role != "investisseur":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux comptes investisseur.")


def _handle_profile_error(exc: Exception) -> HTTPException:
    """Un seul point de mapping erreur métier -> code HTTP, même convention
    que _handle_profile_error côté researcher_profile_router."""
    if isinstance(exc, InvestorProfileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/onboarding", response_model=InvestorProfileRead)
def complete_onboarding(
    body: InvestorOnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestorProfileRead:
    _require_investisseur_role(current_user)
    try:
        return investor_service.complete_onboarding(db, current_user.id, body)
    except InvestorProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.get("/profile", response_model=InvestorProfileRead)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestorProfileRead:
    _require_investisseur_role(current_user)
    try:
        return investor_service.get_by_user_id(db, current_user.id)
    except InvestorProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.patch("/profile", response_model=InvestorProfileRead)
def update_profile(
    body: InvestorProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestorProfileRead:
    _require_investisseur_role(current_user)
    try:
        return investor_service.update_profile(db, current_user.id, body)
    except InvestorProfileNotFoundError as exc:
        raise _handle_profile_error(exc)

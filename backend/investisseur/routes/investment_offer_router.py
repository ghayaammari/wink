"""Routes de `investment_offers` — CRUD simple (dépôt/liste/fermeture),

scopé à l'investor_profile de l'utilisateur connecté. Fichier distinct de
investisseur_matching_router.py (déclenchement/lecture du matching, marquage
"intéressé") -- même séparation que research_need_router.py /
chercheur_matching_router.py côté entrepreneur.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.investisseur.schemas.investment_offer_schemas import (
    InvestmentOfferCreate,
    InvestmentOfferRead,
    InvestmentOfferStatutUpdate,
)
from backend.investisseur.services.investment_offer_service import (
    InvestmentOfferNotFoundError,
    create_offer,
    get_owned_offer,
    list_offers,
    update_statut,
)
from backend.investisseur.services.investor_service import InvestorProfileNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/investisseur/offres", tags=["investisseur-offres"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (InvestmentOfferNotFoundError, InvestorProfileNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=InvestmentOfferRead, status_code=status.HTTP_201_CREATED)
def deposer_offre(
    body: InvestmentOfferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferRead:
    try:
        return create_offer(
            db,
            current_user,
            body.titre,
            body.description,
            body.montant_propose,
            body.secteurs_cibles,
            body.stades_cibles,
        )
    except InvestorProfileNotFoundError as exc:
        raise _handle_error(exc)


@router.get("", response_model=list[InvestmentOfferRead])
def lister_offres(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvestmentOfferRead]:
    try:
        return list_offers(db, current_user)
    except InvestorProfileNotFoundError as exc:
        raise _handle_error(exc)


@router.get("/{offer_id}", response_model=InvestmentOfferRead)
def lire_offre(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferRead:
    try:
        return get_owned_offer(db, current_user, offer_id)
    except (InvestmentOfferNotFoundError, InvestorProfileNotFoundError) as exc:
        raise _handle_error(exc)


@router.patch("/{offer_id}", response_model=InvestmentOfferRead)
def fermer_offre(
    offer_id: UUID,
    body: InvestmentOfferStatutUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferRead:
    try:
        return update_statut(db, current_user, offer_id, body.statut)
    except (InvestmentOfferNotFoundError, InvestorProfileNotFoundError) as exc:
        raise _handle_error(exc)

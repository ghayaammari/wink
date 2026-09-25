"""Routes du matching Investisseur-Startup pour une offre donnée

(investment_offers, EPIC-07) — déclenchement, lecture du résultat,
marquage "intéressé", et liste transversale des recommandations
intéressantes. Même séparation que chercheur_matching_router.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.shared.groq_runtime.react_agent_runner import ReactAgentError
from backend.investisseur.schemas.investment_offer_match_schemas import (
    InteretUpdate,
    InvestmentOfferMatchRead,
    StartupInteressanteRead,
)
from backend.investisseur.services.investisseur_matching_orchestration_service import run_matching
from backend.investisseur.services.investment_offer_match_service import (
    MatchNotFoundError,
    enrichir_resultat,
    get_result,
    list_interesting_matches_enrichies,
    toggle_interet,
)
from backend.investisseur.services.investment_offer_service import InvestmentOfferNotFoundError, get_owned_offer
from backend.investisseur.services.investor_service import InvestorProfileNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/investisseur/offres", tags=["investisseur-matching"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (InvestmentOfferNotFoundError, InvestorProfileNotFoundError, MatchNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ReactAgentError):
        # Échec Groq/LangGraph -- pas une erreur de requête client, 502
        # plutôt que 400 (même convention que chercheur_matching_router.py).
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{offer_id}/startups", response_model=InvestmentOfferMatchRead)
def lancer_matching_startups(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferMatchRead:
    try:
        row = run_matching(db, current_user, offer_id)
        return enrichir_resultat(db, row)
    except (InvestmentOfferNotFoundError, InvestorProfileNotFoundError, ReactAgentError) as exc:
        raise _handle_error(exc)


@router.get("/{offer_id}/startups", response_model=InvestmentOfferMatchRead | None)
def lire_matching_startups(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferMatchRead | None:
    try:
        offer = get_owned_offer(db, current_user, offer_id)
        row = get_result(db, offer.id)
        return enrichir_resultat(db, row) if row is not None else None
    except (InvestmentOfferNotFoundError, InvestorProfileNotFoundError) as exc:
        raise _handle_error(exc)


@router.patch("/{offer_id}/startups/{project_id}/interet", response_model=InvestmentOfferMatchRead)
def marquer_interet_startup(
    offer_id: UUID,
    project_id: UUID,
    payload: InteretUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentOfferMatchRead:
    try:
        offer = get_owned_offer(db, current_user, offer_id)
        row = toggle_interet(db, offer.id, project_id, payload.interesse)
        return enrichir_resultat(db, row)
    except (InvestmentOfferNotFoundError, InvestorProfileNotFoundError, MatchNotFoundError) as exc:
        raise _handle_error(exc)


@router.get("/interessantes", response_model=list[StartupInteressanteRead])
def lister_startups_interessantes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StartupInteressanteRead]:
    try:
        return list_interesting_matches_enrichies(db, current_user)
    except InvestorProfileNotFoundError as exc:
        raise _handle_error(exc)

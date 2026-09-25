"""Routes du matching Startup-Offres pour LE PROJET d'un entrepreneur

(EPIC-06) — déclenchement, lecture du résultat, marquage "intéressé" d'une
offre, et liste des offres intéressantes. Sens inverse de investisseur_
matching_router.py, même séparation.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.shared.groq_runtime.react_agent_runner import ReactAgentError
from backend.entrepreneur.schemas.project_offer_match_schemas import (
    InteretUpdate,
    OfferMatchRead,
    ProjectOfferMatchRead,
)
from backend.entrepreneur.services.project_offer_match_service import (
    MatchNotFoundError,
    enrichir_resultat,
    get_result,
    list_offres_interessantes,
    toggle_interet,
)
from backend.entrepreneur.services.project_service import (
    ForbiddenError,
    ProjectError,
    ProjectNotFoundError,
    get_owned_project,
)
from backend.entrepreneur.services.startup_offer_matching_orchestration_service import run_matching
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["matching-startup-offres"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ProjectNotFoundError, MatchNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ReactAgentError):
        # Échec Groq/LangGraph -- pas une erreur de requête client, 502
        # plutôt que 400 (même convention que investisseur_matching_router.py).
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/matching/offres", response_model=ProjectOfferMatchRead)
def lancer_matching_offres(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOfferMatchRead:
    try:
        row = run_matching(db, current_user, project_id)
        return enrichir_resultat(db, row)
    except (ProjectError, ReactAgentError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/matching/offres", response_model=ProjectOfferMatchRead | None)
def lire_matching_offres(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOfferMatchRead | None:
    try:
        get_owned_project(db, current_user, project_id)
        row = get_result(db, project_id)
        return enrichir_resultat(db, row) if row is not None else None
    except ProjectError as exc:
        raise _handle_error(exc)


@router.patch("/{project_id}/matching/offres/{offer_id}/interet", response_model=ProjectOfferMatchRead)
def marquer_interet_offre(
    project_id: UUID,
    offer_id: UUID,
    payload: InteretUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOfferMatchRead:
    try:
        get_owned_project(db, current_user, project_id)
        row = toggle_interet(db, project_id, offer_id, payload.interesse)
        return enrichir_resultat(db, row)
    except (ProjectError, MatchNotFoundError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/matching/offres/interessantes", response_model=list[OfferMatchRead])
def lister_offres_interessantes(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OfferMatchRead]:
    try:
        get_owned_project(db, current_user, project_id)
        return list_offres_interessantes(db, project_id)
    except ProjectError as exc:
        raise _handle_error(exc)

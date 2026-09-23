"""Routes du matching Recherche-Startup pour un besoin donné (research_
needs, service 7.7.2) — fichier distinct de research_need_router.py (CRUD
simple du besoin) : ce routeur ne gère que le déclenchement, la lecture du
résultat de l'agent, le marquage "intéressé" d'une recommandation, et la
liste transversale des recommandations intéressantes, même séparation que
les routers *_diagnostic côté compliance_agent.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.shared.groq_runtime.react_agent_runner import ReactAgentError
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.matching.schemas.research_need_match_schemas import (
    InteretUpdate,
    RecommandationInteressanteRead,
    ResearchNeedMatchRead,
)
from backend.matching.services.chercheur_matching_orchestration_service import run_matching
from backend.matching.services.research_need_match_service import (
    MatchNotFoundError,
    get_owned_need,
    get_result,
    list_interesting_matches,
    toggle_interet,
)
from backend.matching.services.research_need_service import ResearchNeedNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["matching-chercheur"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ProjectNotFoundError, ResearchNeedNotFoundError, MatchNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ReactAgentError):
        # Échec Groq/LangGraph (quota épuisé, réponse hors schéma...) — pas
        # une erreur de requête client, 502 plutôt que 400.
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/matching/research-needs/{need_id}/chercheurs", response_model=ResearchNeedMatchRead)
def lancer_matching_chercheurs(
    project_id: UUID,
    need_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchNeedMatchRead:
    try:
        return run_matching(db, current_user, project_id, need_id)
    except (ProjectError, ResearchNeedNotFoundError, ReactAgentError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/matching/research-needs/{need_id}/chercheurs", response_model=ResearchNeedMatchRead | None)
def lire_matching_chercheurs(
    project_id: UUID,
    need_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchNeedMatchRead | None:
    try:
        need = get_owned_need(db, current_user, project_id, need_id)
        return get_result(db, need.id)
    except (ProjectError, ResearchNeedNotFoundError) as exc:
        raise _handle_error(exc)


@router.patch(
    "/{project_id}/matching/research-needs/{need_id}/chercheurs/{researcher_profile_id}/interet",
    response_model=ResearchNeedMatchRead,
)
def marquer_interet_chercheur(
    project_id: UUID,
    need_id: UUID,
    researcher_profile_id: UUID,
    payload: InteretUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchNeedMatchRead:
    try:
        need = get_owned_need(db, current_user, project_id, need_id)
        return toggle_interet(db, need.id, researcher_profile_id, payload.interesse)
    except (ProjectError, ResearchNeedNotFoundError, MatchNotFoundError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/matching/recommandations-interessantes", response_model=list[RecommandationInteressanteRead])
def lister_recommandations_interessantes(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommandationInteressanteRead]:
    try:
        return list_interesting_matches(db, current_user, project_id)
    except (ProjectError,) as exc:
        raise _handle_error(exc)

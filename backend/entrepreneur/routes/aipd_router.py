"""Routes du service AIPD (3.3.4) — fichier distinct de rgpd_router.py

(3.3.1) : responsabilité différente (générateur d'analyse d'impact), même si
déclenché depuis la même carte RGPD côté frontend (voir
Wink_architecture_fichiers.md, règle "un fichier, une responsabilité").
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.compliance_agent.rgpd_service import RgpdAgentError
from backend.entrepreneur.schemas.aipd_analysis_schemas import AipdAnalysisRead
from backend.entrepreneur.services import aipd_analysis_service
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-aipd"])


def _handle_aipd_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_rgpd_error (rgpd_router.py) — un seul point

    de mapping erreur métier -> code HTTP pour ce fichier.
    """
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, RgpdAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/rgpd/aipd", response_model=list[AipdAnalysisRead])
def get_aipd_analyses(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AipdAnalysisRead]:
    try:
        return aipd_analysis_service.list_analyses(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_aipd_error(exc)


@router.post("/{project_id}/rgpd/aipd", response_model=AipdAnalysisRead)
def generer_aipd(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AipdAnalysisRead:
    try:
        return aipd_analysis_service.generate_analysis(db, current_user, project_id)
    except (ProjectError, RgpdAgentError) as exc:
        raise _handle_aipd_error(exc)

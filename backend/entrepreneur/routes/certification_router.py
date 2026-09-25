"""Routes du service Certifications de sécurité (3.3.11). Fichier distinct de

rgpd_router.py/ai_act_router.py/sector_router.py : responsabilité différente
(voir Wink_architecture_fichiers.md, un fichier de routes par domaine).

V1 limitée à SecNumCloud, en dur dans le préfixe d'URL (`/certification/
secnumcloud/...`, pas `/certification/{type}/...`) -- reflète honnêtement
que seul ce type existe côté service pour l'instant (voir
project_certification_obligation_service.py). Le préfixe deviendra
`/certification/{type_certification}/...` quand ISO 27001/SOC 2 seront
ajoutés, pas avant.

POST .../diagnostic (ajoutée le 22/09/2026 avec le 6e sous-agent de
compliance_agent) : même convention que rgpd_router.recalculer_diagnostic_rgpd
-- renvoie les étapes du parcours (l'estimation, générée dans le même appel
agent, se récupère séparément via GET .../estimation, même principe que le
score : le frontend affiche les deux widgets indépendamment).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.compliance_agent.secnumcloud_service import SecnumcloudAgentError
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.project_certification_estimation_schemas import ProjectCertificationEstimationRead
from backend.entrepreneur.schemas.project_certification_obligation_schemas import (
    ProjectCertificationObligationRead,
    ProjectCertificationObligationStatutUpdate,
)
from backend.entrepreneur.services import project_certification_estimation_service, project_certification_obligation_service
from backend.entrepreneur.services.project_certification_obligation_service import (
    CertificationObligationNotFoundError,
)
from backend.entrepreneur.services.project_service import (
    ForbiddenError,
    ProjectError,
    ProjectNotFoundError,
    get_owned_project,
)
from backend.entrepreneur.services.secnumcloud_diagnostic_service import run_diagnostic
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-certification"])


def _handle_certification_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_rgpd_error (rgpd_router.py). SecnumcloudAgentError

    (échec Groq après retries, réponse invalide) traduite en 502 : la faute
    vient d'une dépendance externe, pas d'une requête client invalide."""
    if isinstance(exc, (ProjectNotFoundError, CertificationObligationNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, SecnumcloudAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/certification/secnumcloud/obligations", response_model=list[ProjectCertificationObligationRead])
def list_secnumcloud_obligations(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectCertificationObligationRead]:
    try:
        return project_certification_obligation_service.list_obligations(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_certification_error(exc)


@router.patch(
    "/{project_id}/certification/secnumcloud/obligations/{obligation_id}",
    response_model=ProjectCertificationObligationRead,
)
def update_secnumcloud_obligation_statut(
    project_id: UUID,
    obligation_id: UUID,
    body: ProjectCertificationObligationStatutUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectCertificationObligationRead:
    try:
        return project_certification_obligation_service.mark_statut(
            db, current_user, project_id, obligation_id, body.statut
        )
    except (ProjectError, CertificationObligationNotFoundError) as exc:
        raise _handle_certification_error(exc)


@router.get("/{project_id}/certification/secnumcloud/score", response_model=ComplianceScoreRead)
def get_secnumcloud_score(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceScoreRead:
    try:
        return project_certification_obligation_service.get_score(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_certification_error(exc)


@router.post("/{project_id}/certification/secnumcloud/diagnostic", response_model=list[ProjectCertificationObligationRead])
def generer_parcours_secnumcloud(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectCertificationObligationRead]:
    try:
        obligations, _estimation = run_diagnostic(db, current_user, project_id)
        return obligations
    except (ProjectError, SecnumcloudAgentError) as exc:
        raise _handle_certification_error(exc)


@router.get("/{project_id}/certification/secnumcloud/estimation", response_model=ProjectCertificationEstimationRead | None)
def get_secnumcloud_estimation(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectCertificationEstimationRead | None:
    try:
        project = get_owned_project(db, current_user, project_id)
        return project_certification_estimation_service.get_estimation(db, project.id)
    except ProjectError as exc:
        raise _handle_certification_error(exc)

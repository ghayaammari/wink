"""Routes du service AI Act (3.3.12) — profil d'usage de l'IA, classification

de risque, liste des obligations, recalcul du diagnostic. Fichier distinct de
rgpd_router.py : responsabilité différente (AI Act), voir
Wink_architecture_fichiers.md.

Recalcul explicite : POST /projects/{id}/ai-act/diagnostic déclenché par un
bouton dédié côté frontend, jamais automatiquement après chaque PATCH du
profil — même raisonnement que rgpd_router.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.compliance_agent.ai_act_service import AiActAgentError
from backend.entrepreneur.schemas.ai_act_data_profile_schemas import AiActDataProfileRead, AiActDataProfileUpdate
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.project_ai_act_classification_schemas import ProjectAiActClassificationRead
from backend.entrepreneur.schemas.project_ai_act_obligation_schemas import (
    AiActDiagnosticRunResult,
    ProjectAiActObligationRead,
    ProjectAiActObligationStatutUpdate,
)
from backend.entrepreneur.services import ai_act_data_profile_service, project_ai_act_obligation_service
from backend.entrepreneur.services.ai_act_diagnostic_service import run_diagnostic
from backend.entrepreneur.services.project_ai_act_classification_service import get_or_create_classification
from backend.entrepreneur.services.project_ai_act_obligation_service import AiActObligationNotFoundError
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-ai-act"])


def _handle_ai_act_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_rgpd_error (rgpd_router.py)."""
    if isinstance(exc, (ProjectNotFoundError, AiActObligationNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, AiActAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/ai-act/profile", response_model=AiActDataProfileRead)
def get_ai_act_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiActDataProfileRead:
    try:
        return ai_act_data_profile_service.get_or_create_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)


@router.patch("/{project_id}/ai-act/profile", response_model=AiActDataProfileRead)
def update_ai_act_profile(
    project_id: UUID,
    body: AiActDataProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiActDataProfileRead:
    try:
        return ai_act_data_profile_service.update_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)


@router.get("/{project_id}/ai-act/classification", response_model=ProjectAiActClassificationRead)
def get_ai_act_classification(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAiActClassificationRead:
    try:
        return get_or_create_classification(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)


@router.get("/{project_id}/ai-act/obligations", response_model=list[ProjectAiActObligationRead])
def get_ai_act_obligations(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectAiActObligationRead]:
    try:
        return project_ai_act_obligation_service.list_obligations(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)


@router.patch("/{project_id}/ai-act/obligations/{obligation_id}", response_model=ProjectAiActObligationRead)
def update_ai_act_obligation_statut(
    project_id: UUID,
    obligation_id: UUID,
    body: ProjectAiActObligationStatutUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAiActObligationRead:
    try:
        return project_ai_act_obligation_service.mark_statut(db, current_user, project_id, obligation_id, body.statut)
    except (ProjectError, AiActObligationNotFoundError) as exc:
        raise _handle_ai_act_error(exc)


@router.post("/{project_id}/ai-act/diagnostic", response_model=AiActDiagnosticRunResult)
def recalculer_diagnostic_ai_act(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiActDiagnosticRunResult:
    try:
        return run_diagnostic(db, current_user, project_id)
    except (ProjectError, AiActAgentError) as exc:
        raise _handle_ai_act_error(exc)


@router.get("/{project_id}/ai-act/score", response_model=ComplianceScoreRead)
def get_ai_act_score(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceScoreRead:
    try:
        return project_ai_act_obligation_service.get_score(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)
@router.get("/{project_id}/ai-act/report")
def get_ai_act_report(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = project_ai_act_obligation_service.get_report_pdf(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_ai_act_error(exc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport-conformite-ai-act.pdf"},
    )

"""Routes du service RGPD (3.3.1) — profil de traitement de données, liste des

obligations, recalcul du diagnostic. Fichier distinct de roadmap_router.py /
project_router.py : responsabilité différente (RGPD), voir
Wink_architecture_fichiers.md.

Recalcul explicite : POST /projects/{id}/rgpd/diagnostic est appelé par un
bouton dédié côté frontend ("Recalculer mes obligations"), jamais
automatiquement après chaque PATCH du profil — un appel LLM (Groq) à chaque
case cochée serait coûteux et inutile tant que l'entrepreneur n'a pas fini de
répondre au diagnostic (voir échange du 16-17/09).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.compliance_agent.rgpd_service import RgpdAgentError
from backend.entrepreneur.schemas.compliance_data_profile_schemas import (
    ComplianceDataProfileRead,
    ComplianceDataProfileUpdate,
)
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.project_rgpd_obligation_schemas import (
    ProjectRgpdObligationRead,
    ProjectRgpdObligationStatutUpdate,
)
from backend.entrepreneur.services import compliance_data_profile_service, project_rgpd_obligation_service
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.entrepreneur.services.project_rgpd_obligation_service import RgpdObligationNotFoundError
from backend.entrepreneur.services.rgpd_diagnostic_service import run_diagnostic
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-rgpd"])


def _handle_rgpd_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_roadmap_error/_handle_project_error — un

    seul point de mapping erreur métier -> code HTTP. RgpdAgentError
    (échec Groq après retries, réponse invalide) est traduite en 502 : la
    faute vient d'une dépendance externe, pas d'une requête client invalide.
    """
    if isinstance(exc, (ProjectNotFoundError, RgpdObligationNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, RgpdAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/rgpd/profile", response_model=ComplianceDataProfileRead)
def get_rgpd_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceDataProfileRead:
    try:
        return compliance_data_profile_service.get_or_create_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_rgpd_error(exc)


@router.patch("/{project_id}/rgpd/profile", response_model=ComplianceDataProfileRead)
def update_rgpd_profile(
    project_id: UUID,
    body: ComplianceDataProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceDataProfileRead:
    try:
        return compliance_data_profile_service.update_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_rgpd_error(exc)


@router.get("/{project_id}/rgpd/obligations", response_model=list[ProjectRgpdObligationRead])
def get_rgpd_obligations(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectRgpdObligationRead]:
    try:
        return project_rgpd_obligation_service.list_obligations(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_rgpd_error(exc)


@router.patch("/{project_id}/rgpd/obligations/{obligation_id}", response_model=ProjectRgpdObligationRead)
def update_rgpd_obligation_statut(
    project_id: UUID,
    obligation_id: UUID,
    body: ProjectRgpdObligationStatutUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRgpdObligationRead:
    try:
        return project_rgpd_obligation_service.mark_statut(db, current_user, project_id, obligation_id, body.statut)
    except (ProjectError, RgpdObligationNotFoundError) as exc:
        raise _handle_rgpd_error(exc)


@router.post("/{project_id}/rgpd/diagnostic", response_model=list[ProjectRgpdObligationRead])
def recalculer_diagnostic_rgpd(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectRgpdObligationRead]:
    try:
        return run_diagnostic(db, current_user, project_id)
    except (ProjectError, RgpdAgentError) as exc:
        raise _handle_rgpd_error(exc)


@router.get("/{project_id}/rgpd/score", response_model=ComplianceScoreRead)
def get_rgpd_score(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceScoreRead:
    try:
        return project_rgpd_obligation_service.get_score(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_rgpd_error(exc)
@router.get("/{project_id}/rgpd/report")
def get_rgpd_report(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = project_rgpd_obligation_service.get_report_pdf(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_rgpd_error(exc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport-conformite-rgpd.pdf"},
    )

"""Routes du service de conformité sectorielle (3.3.5) — détection du secteur

réglementé, profils et classifications HealthTech/FinTech. Fichier distinct
de `ai_act_router.py`/`rgpd_router.py` : responsabilité différente (secteur),
voir Wink_architecture_fichiers.md.

Détection : POST /projects/{id}/sector/detection déclenché par un bouton
dédié côté frontend (appel LLM, même raisonnement que le diagnostic AI Act).
Classifications HealthTech/FinTech : pas de POST de recalcul — elles se
recalculent automatiquement à chaque PATCH du profil correspondant (calcul
déterministe gratuit, voir docstring `project_healthtech_classification_
service.py`), donc seul un GET est exposé ici.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.compliance_agent.sector_detection_service import SectorDetectionAgentError
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.fintech_data_profile_schemas import FintechDataProfileRead, FintechDataProfileUpdate
from backend.entrepreneur.schemas.healthtech_data_profile_schemas import (
    HealthtechDataProfileRead,
    HealthtechDataProfileUpdate,
)
from backend.entrepreneur.schemas.project_fintech_classification_schemas import ProjectFintechClassificationRead
from backend.entrepreneur.schemas.project_healthtech_classification_schemas import (
    ProjectHealthtechClassificationRead,
)
from backend.entrepreneur.schemas.project_healthtech_gap_analysis_schemas import (
    ChapitreGapAnalysisStatusRead,
    ChapitreHealthtech,
    ObligationToggleUpdate as HealthtechObligationToggleUpdate,
)
from backend.entrepreneur.schemas.project_sector_detection_schemas import ProjectSectorDetectionRead
from backend.entrepreneur.services import fintech_data_profile_service, healthtech_data_profile_service
from backend.entrepreneur.services.project_fintech_classification_service import (
    get_or_create_classification as get_or_create_fintech_classification,
)
from backend.entrepreneur.services.project_healthtech_classification_service import (
    get_or_create_classification as get_or_create_healthtech_classification,
)
from agents.compliance_agent.healthtech_gap_analysis_service import HealthtechGapAnalysisError
from backend.entrepreneur.services.healthtech_gap_analysis_diagnostic_service import run_chapter_diagnostic
from backend.entrepreneur.services.project_healthtech_gap_analysis_service import (
    ChapitreGapAnalysisInconnuError,
    ChapitreGapAnalysisVerrouilleError,
    ObligationIndexInvalideError as HealthtechObligationIndexInvalideError,
    get_chapter_status_list,
    get_report_pdf as get_healthtech_report_pdf,
    get_score as get_healthtech_score,
    toggle_obligation as toggle_healthtech_obligation,
)
from agents.compliance_agent.fintech_gap_analysis_service import FintechGapAnalysisError
from backend.entrepreneur.schemas.project_fintech_gap_analysis_schemas import (
    ObligationToggleUpdate as FintechObligationToggleUpdate,
    ProjectFintechGapAnalysisRead,
)
from backend.entrepreneur.services.fintech_gap_analysis_diagnostic_service import run_diagnostic as run_fintech_diagnostic
from backend.entrepreneur.services.project_fintech_gap_analysis_service import (
    FintechGapAnalysisVerrouilleError,
    ObligationIndexInvalideError as FintechObligationIndexInvalideError,
    get_result as get_fintech_gap_analysis_result,
    get_report_pdf as get_fintech_report_pdf,
    get_score as get_fintech_score,
    toggle_obligation as toggle_fintech_obligation,
)
from backend.entrepreneur.services.project_sector_detection_service import get_or_create_detection
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.entrepreneur.services.sector_detection_diagnostic_service import run_detection
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-sector"])


def _handle_sector_error(exc: Exception) -> HTTPException:
    """Même principe que _handle_ai_act_error (ai_act_router.py)."""
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, SectorDetectionAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, HealthtechGapAnalysisError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, ChapitreGapAnalysisInconnuError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ChapitreGapAnalysisVerrouilleError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, FintechGapAnalysisError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, FintechGapAnalysisVerrouilleError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (HealthtechObligationIndexInvalideError, FintechObligationIndexInvalideError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/sector/detection", response_model=ProjectSectorDetectionRead)
def get_sector_detection(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSectorDetectionRead:
    try:
        return get_or_create_detection(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.post("/{project_id}/sector/detection", response_model=ProjectSectorDetectionRead)
def recalculer_sector_detection(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSectorDetectionRead:
    try:
        return run_detection(db, current_user, project_id)
    except (ProjectError, SectorDetectionAgentError) as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/healthtech/profile", response_model=HealthtechDataProfileRead)
def get_healthtech_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HealthtechDataProfileRead:
    try:
        return healthtech_data_profile_service.get_or_create_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.patch("/{project_id}/sector/healthtech/profile", response_model=HealthtechDataProfileRead)
def update_healthtech_profile(
    project_id: UUID,
    body: HealthtechDataProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HealthtechDataProfileRead:
    try:
        return healthtech_data_profile_service.update_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/healthtech/classification", response_model=ProjectHealthtechClassificationRead)
def get_healthtech_classification(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectHealthtechClassificationRead:
    try:
        return get_or_create_healthtech_classification(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/fintech/profile", response_model=FintechDataProfileRead)
def get_fintech_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FintechDataProfileRead:
    try:
        return fintech_data_profile_service.get_or_create_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.patch("/{project_id}/sector/fintech/profile", response_model=FintechDataProfileRead)
def update_fintech_profile(
    project_id: UUID,
    body: FintechDataProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FintechDataProfileRead:
    try:
        return fintech_data_profile_service.update_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/fintech/classification", response_model=ProjectFintechClassificationRead)
def get_fintech_classification(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFintechClassificationRead:
    try:
        return get_or_create_fintech_classification(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/healthtech/gap-analysis", response_model=list[ChapitreGapAnalysisStatusRead])
def get_healthtech_gap_analysis(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChapitreGapAnalysisStatusRead]:
    try:
        return get_chapter_status_list(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.post("/{project_id}/sector/healthtech/gap-analysis/{chapitre}", response_model=ChapitreGapAnalysisStatusRead)
def generer_healthtech_gap_analysis_chapitre(
    project_id: UUID,
    chapitre: ChapitreHealthtech,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChapitreGapAnalysisStatusRead:
    try:
        run_chapter_diagnostic(db, current_user, project_id, chapitre)
        statuses = get_chapter_status_list(db, current_user, project_id)
    except (
        ProjectError,
        HealthtechGapAnalysisError,
        ChapitreGapAnalysisInconnuError,
        ChapitreGapAnalysisVerrouilleError,
    ) as exc:
        raise _handle_sector_error(exc)
    return next(s for s in statuses if s.cle == chapitre)


@router.get("/{project_id}/sector/fintech/gap-analysis", response_model=ProjectFintechGapAnalysisRead | None)
def get_fintech_gap_analysis(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFintechGapAnalysisRead | None:
    """Retourne None tant qu'aucune génération n'a été déclenchée — pas de

    chapitres/verrouillage côté FinTech (bloc unique), voir docstring
    project_fintech_gap_analysis_service.py."""
    try:
        return get_fintech_gap_analysis_result(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.post("/{project_id}/sector/fintech/gap-analysis", response_model=ProjectFintechGapAnalysisRead)
def generer_fintech_gap_analysis(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFintechGapAnalysisRead:
    try:
        return run_fintech_diagnostic(db, current_user, project_id)
    except (ProjectError, FintechGapAnalysisError, FintechGapAnalysisVerrouilleError) as exc:
        raise _handle_sector_error(exc)


@router.patch(
    "/{project_id}/sector/healthtech/gap-analysis/{chapitre}/obligations/{obligation_index}",
    response_model=ChapitreGapAnalysisStatusRead,
)
def toggler_obligation_healthtech(
    project_id: UUID,
    chapitre: ChapitreHealthtech,
    obligation_index: int,
    body: HealthtechObligationToggleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChapitreGapAnalysisStatusRead:
    try:
        toggle_healthtech_obligation(db, current_user, project_id, chapitre, obligation_index, body.accompli)
        statuses = get_chapter_status_list(db, current_user, project_id)
    except (
        ProjectError,
        ChapitreGapAnalysisInconnuError,
        HealthtechObligationIndexInvalideError,
    ) as exc:
        raise _handle_sector_error(exc)
    return next(s for s in statuses if s.cle == chapitre)


@router.patch(
    "/{project_id}/sector/fintech/gap-analysis/obligations/{obligation_index}",
    response_model=ProjectFintechGapAnalysisRead,
)
def toggler_obligation_fintech(
    project_id: UUID,
    obligation_index: int,
    body: FintechObligationToggleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectFintechGapAnalysisRead:
    try:
        return toggle_fintech_obligation(db, current_user, project_id, obligation_index, body.accompli)
    except (ProjectError, FintechObligationIndexInvalideError) as exc:
        raise _handle_sector_error(exc)
@router.get("/{project_id}/sector/healthtech/gap-analysis/score", response_model=ComplianceScoreRead)
def get_healthtech_gap_analysis_score(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceScoreRead:
    try:
        return get_healthtech_score(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)


@router.get("/{project_id}/sector/fintech/gap-analysis/score", response_model=ComplianceScoreRead)
def get_fintech_gap_analysis_score(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceScoreRead:
    try:
        return get_fintech_score(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)
@router.get("/{project_id}/sector/healthtech/gap-analysis/report")
def get_healthtech_gap_analysis_report(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = get_healthtech_report_pdf(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport-conformite-healthtech.pdf"},
    )


@router.get("/{project_id}/sector/fintech/gap-analysis/report")
def get_fintech_gap_analysis_report(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = get_fintech_report_pdf(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_sector_error(exc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport-conformite-fintech.pdf"},
    )

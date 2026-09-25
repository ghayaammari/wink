"""Routes du service 1.1.5 — annonce légale de constitution.

GET   /projects/{id}/legal-announcement               état complet (annonce, problèmes, avertissements)
POST  /projects/{id}/legal-announcement/generate      génère ou régénère le texte
PATCH /projects/{id}/legal-announcement               corrige le texte (relecture)
POST  /projects/{id}/legal-announcement/validate      valide le texte
GET   /projects/{id}/legal-announcement/journals      journaux habilités du département du siège
POST  /projects/{id}/legal-announcement/attestation   dépose l'attestation de parution (multipart)

Fichier distinct : responsabilité propre au 1.1.5 (voir
Wink_architecture_fichiers.md). Toute la logique est dans
`legal_announcement_service.py` ; ici, uniquement le mapping HTTP.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.legal_announcement_schemas import (
    JournauxHabilitesRead,
    LegalAnnouncementRead,
    LegalAnnouncementStateRead,
    LegalAnnouncementTextUpdate,
)
from backend.entrepreneur.services import legal_announcement_service as service
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-legal-announcement"])


def _handle_error(exc: Exception) -> HTTPException:
    """Un seul point de mapping erreur métier -> code HTTP."""
    if isinstance(exc, (ProjectNotFoundError, service.AnnonceIntrouvableError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, service.AnnoncePrevalidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "problemes": exc.problemes},
        )
    if isinstance(exc, service.AnnonceStatutError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, service.AnnonceStockageError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/legal-announcement", response_model=LegalAnnouncementStateRead)
def get_legal_announcement(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_etat_annonce(db, current_user, project_id)
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/legal-announcement/generate", response_model=LegalAnnouncementRead)
def generate_legal_announcement(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.generer_annonce(db, current_user, project_id)
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)


@router.patch("/{project_id}/legal-announcement", response_model=LegalAnnouncementRead)
def update_legal_announcement_text(
    project_id: UUID,
    body: LegalAnnouncementTextUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.modifier_texte(db, current_user, project_id, body.texte_annonce)
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/legal-announcement/validate", response_model=LegalAnnouncementRead)
def validate_legal_announcement(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.valider_annonce(db, current_user, project_id)
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)


@router.get("/{project_id}/legal-announcement/journals", response_model=JournauxHabilitesRead)
def list_habilitated_journals(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return service.lister_journaux(db, current_user, project_id)
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/legal-announcement/attestation", response_model=LegalAnnouncementRead)
async def upload_publication_certificate(
    project_id: UUID,
    file: UploadFile = File(...),
    journal_utilise: str = Form(..., max_length=255),
    date_publication: date = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    try:
        return service.deposer_attestation(
            db,
            current_user,
            project_id,
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type,
            journal_utilise=journal_utilise,
            date_publication=date_publication,
        )
    except (ProjectError, service.AnnonceError) as exc:
        raise _handle_error(exc)

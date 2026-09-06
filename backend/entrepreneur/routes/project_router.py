"""Routes du questionnaire d'onboarding entrepreneur — services 0.0.2, 0.0.3, 0.0.4.

POST /projects, GET /projects/me, GET /projects/{id}, PATCH /projects/{id},
POST /projects/{id}/legal-profile, POST /projects/{id}/upload-logo,
POST /projects/{id}/public-profile.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.project_legal_profile_schemas import (
    ProjectLegalProfileCreate,
    ProjectLegalProfileRead,
    ProjectLegalProfileUpdate,
)
from backend.entrepreneur.schemas.project_public_profile_schemas import (
    ProjectPublicProfileRead,
    ProjectPublicProfileUpdate,
)
from backend.entrepreneur.schemas.project_schemas import ProjectCreate, ProjectRead, ProjectUpdate
from backend.entrepreneur.services import project_service
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-projects"])


def _handle_project_error(exc: ProjectError) -> HTTPException:
    """Traduit les erreurs métier en codes HTTP — un seul point de mapping,

    plutôt que de répéter les try/except dans chaque route.
    """
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        project = project_service.create_project(db, current_user, body.project_type, body.stage)
    except ProjectError as exc:
        raise _handle_project_error(exc)
    return project


@router.get("/me", response_model=ProjectRead | None)
def get_my_project(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead | None:
    # Pas de 404 ici volontairement : absence de projet = état normal juste après
    # signup, utilisé par le frontend pour décider wizard vs accueil (voir docstring
    # get_project_for_user dans project_service.py).
    return project_service.get_project_for_user(db, current_user)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        return project_service.get_project_full(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        return project_service.update_project(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.post(
    "/{project_id}/legal-profile",
    response_model=ProjectLegalProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_legal_profile(
    project_id: UUID,
    body: ProjectLegalProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectLegalProfileRead:
    try:
        return project_service.create_legal_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.get("/{project_id}/legal-profile", response_model=ProjectLegalProfileRead | None)
def get_legal_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectLegalProfileRead | None:
    # Ajouté pour le dashboard "Mon projet" (lecture seule) : aucune route de lecture
    # n'existait encore pour ce profil, seulement la création (voir create_legal_profile
    # ci-dessus). Pas de 404 si absent — voir docstring project_service.get_legal_profile.
    try:
        return project_service.get_legal_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.patch("/{project_id}/legal-profile", response_model=ProjectLegalProfileRead)
def update_legal_profile(
    project_id: UUID,
    body: ProjectLegalProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectLegalProfileRead:
    # Ajouté pour le bouton "Mettre à jour" de "Informations légales" (dashboard "Mon
    # projet") : create_legal_profile ci-dessus échoue si un profil existe déjà, donc pas
    # réutilisable pour une modification — cette route fait un upsert (voir
    # project_service.update_legal_profile).
    try:
        return project_service.update_legal_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.post("/{project_id}/upload-logo")
async def upload_project_logo(
    project_id: UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    file_bytes = await file.read()
    try:
        logo_url = project_service.upload_project_logo(db, current_user, project_id, file_bytes)
    except ProjectError as exc:
        raise _handle_project_error(exc)
    # URL renvoyée seule, pas encore persistée sur project_public_profiles : c'est
    # au frontend d'appeler POST .../public-profile avec cette URL pour l'enregistrer
    # (même découpage que le plan d'implémentation — voir upload_project_logo).
    return {"logo_url": logo_url}


@router.post("/{project_id}/public-profile", response_model=ProjectPublicProfileRead)
def upsert_public_profile(
    project_id: UUID,
    body: ProjectPublicProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPublicProfileRead:
    try:
        return project_service.upsert_public_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.get("/{project_id}/public-profile", response_model=ProjectPublicProfileRead | None)
def get_public_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPublicProfileRead | None:
    # Même ajout que get_legal_profile ci-dessus, pour le dashboard "Mon projet".
    try:
        return project_service.get_public_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)

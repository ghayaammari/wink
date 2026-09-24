"""Routes du questionnaire d'onboarding entrepreneur — services 0.0.2, 0.0.3, 0.0.4.

POST /projects, GET /projects/me, GET /projects/{id}, PATCH /projects/{id},
POST /projects/{id}/legal-profile, POST /projects/{id}/upload-logo,
POST /projects/{id}/public-profile, GET/POST /projects/{id}/officers,
PATCH/DELETE /projects/{id}/officers/{officer_id}.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.company_officer_schemas import (
    CompanyOfficerCreate,
    CompanyOfficerRead,
    CompanyOfficerUpdate,
)
from backend.entrepreneur.schemas.project_associate_schemas import (
    ProjectAssociateBatchItem,
    ProjectAssociateCreate,
    ProjectAssociateRead,
    ProjectAssociateUpdate,
)
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
from backend.entrepreneur.services import (
    associate_service,
    company_officer_service,
    legal_verification_service,
    project_service,
)
from backend.entrepreneur.services.legal_verification_service import (
    LegalVerificationError,
    LegalVerificationUpstreamError,
)
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-projects"])


def _handle_project_error(exc: ProjectError | LegalVerificationError) -> HTTPException:
    """Traduit les erreurs métier en codes HTTP — un seul point de mapping,

    plutôt que de répéter les try/except dans chaque route. Élargi à
    LegalVerificationError pour verify_legal_profile ci-dessous — même
    principe que _handle_error dans name_availability_router.py.
    """
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, LegalVerificationUpstreamError):
        # 503, pas 400 : l'échec vient de l'API Recherche d'Entreprises, pas
        # d'une erreur de saisie de l'utilisateur.
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
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


@router.post("/{project_id}/legal-profile/verify", response_model=ProjectLegalProfileRead)
def verify_legal_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectLegalProfileRead:
    # Route séparée du PATCH ci-dessus, volontairement : sauvegarder ne doit
    # jamais dépendre d'un appel externe qui peut échouer ou être lent (voir
    # legal_verification_service). Appelée par UpdateLegalProfileForm.tsx juste
    # après la sauvegarde, uniquement pour Parcours B (project_type="created").
    # Cœur réutilisé tel quel par le futur job périodique de 1.1.9 (Parcours A).
    try:
        return legal_verification_service.verify_legal_profile(db, current_user, project_id)
    except (ProjectError, LegalVerificationError) as exc:
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


# ---------------------------------------------------------------------------
# Équipe & capital — `project_associates` (socle Groupe 5, partagé 1.1.4/1.1.6/1.1.13)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/associates", response_model=list[ProjectAssociateRead])
def list_associates(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectAssociateRead]:
    # La ligne du fondateur est matérialisée ici si absente (associé = propriétaire,
    # 100 % solo, dirigeant) — voir ensure_founder_associate dans associate_service.
    try:
        return associate_service.list_associates(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.post("/{project_id}/associates", response_model=ProjectAssociateRead, status_code=status.HTTP_201_CREATED)
def create_associate(
    project_id: UUID,
    body: ProjectAssociateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAssociateRead:
    try:
        return associate_service.create_associate(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.put("/{project_id}/associates", response_model=list[ProjectAssociateRead])
def replace_associates(
    project_id: UUID,
    body: list[ProjectAssociateBatchItem],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectAssociateRead]:
    # Enregistrement GLOBAL de la page "Équipe & capital" : la liste complète est
    # envoyée au clic "Enregistrer", et la règle bloquante "somme = 100 %" +
    # "≥ 1 dirigeant" est validée sur l'état cible par replace_associates.
    # (réalisé par OPENCODE)
    try:
        return associate_service.replace_associates(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.patch("/{project_id}/associates/{associate_id}", response_model=ProjectAssociateRead)
def update_associate(
    project_id: UUID,
    associate_id: UUID,
    body: ProjectAssociateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectAssociateRead:
    try:
        return associate_service.update_associate(db, current_user, project_id, associate_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.delete(
    "/{project_id}/associates/{associate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_associate(
    project_id: UUID,
    associate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        associate_service.delete_associate(db, current_user, project_id, associate_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)


# ---------------------------------------------------------------------------
# Dirigeants — `company_officers` (service 1.1.4, lot 5 du 24/09/2026) :
# Président, Directeur Général, membres du comité, mandataire (art. 39-41, 44).
# Ici plutôt qu'un router dédié : sous-ressource du projet, même famille que
# /legal-profile et /associates.
# ---------------------------------------------------------------------------

@router.get("/{project_id}/officers", response_model=list[CompanyOfficerRead])
def list_officers(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyOfficerRead]:
    try:
        return company_officer_service.list_officers(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.post("/{project_id}/officers", response_model=CompanyOfficerRead, status_code=status.HTTP_201_CREATED)
def create_officer(
    project_id: UUID,
    body: CompanyOfficerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOfficerRead:
    # Une action = un enregistrement (bouton « Ajouter » de la page Dirigeants).
    try:
        return company_officer_service.create_officer(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.patch("/{project_id}/officers/{officer_id}", response_model=CompanyOfficerRead)
def update_officer(
    project_id: UUID,
    officer_id: UUID,
    body: CompanyOfficerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOfficerRead:
    try:
        return company_officer_service.update_officer(db, current_user, project_id, officer_id, body)
    except ProjectError as exc:
        raise _handle_project_error(exc)


@router.delete("/{project_id}/officers/{officer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_officer(
    project_id: UUID,
    officer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        company_officer_service.delete_officer(db, current_user, project_id, officer_id)
    except ProjectError as exc:
        raise _handle_project_error(exc)

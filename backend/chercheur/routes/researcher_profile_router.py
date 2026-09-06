"""Routes du profil chercheur — services 0.0.2 à 0.0.4 (volet onboarding et
profil métier).

POST /chercheur/onboarding, GET /chercheur/profile, PATCH /chercheur/profile
(modification post-onboarding), DELETE .../expertise-summary et
.../research-work-summary (effacement pour régénération propre), et
déclenchement des résumés générés par LLM.

Extraction HAL/OpenAlex et dépôt manuel de travaux vivent dans
research_work_router.py, pas ici — routes propres à research_works, pas au
profil lui-même. L'onboarding ne déclenche plus l'extraction automatiquement
(voir researcher_profile_service.complete_onboarding) — BackgroundTasks n'est
donc plus nécessaire sur cette route.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.chercheur.schemas.researcher_profile_schemas import (
    ResearcherOnboardingRequest,
    ResearcherProfileRead,
    ResearcherProfileUpdateRequest,
)
from backend.chercheur.services import researcher_profile_service, researcher_summary_service
from backend.chercheur.services.researcher_profile_service import (
    MissingOrcidError,
    ResearcherProfileNotFoundError,
)
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/chercheur", tags=["chercheur-profile"])


def _handle_profile_error(exc: Exception) -> HTTPException:
    """Traduit les erreurs métier en codes HTTP — un seul point de mapping,
    même convention que _handle_project_error côté entrepreneur."""
    if isinstance(exc, ResearcherProfileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, MissingOrcidError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _require_chercheur_role(current_user: User) -> None:
    if current_user.role != "chercheur":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux comptes chercheur.",
        )


@router.post("/onboarding", response_model=ResearcherProfileRead)
def complete_onboarding(
    body: ResearcherOnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherProfileRead:
    _require_chercheur_role(current_user)
    try:
        return researcher_profile_service.complete_onboarding(db, current_user.id, body)
    except (ResearcherProfileNotFoundError, MissingOrcidError) as exc:
        raise _handle_profile_error(exc)


@router.get("/profile", response_model=ResearcherProfileRead)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherProfileRead:
    _require_chercheur_role(current_user)
    try:
        return researcher_profile_service.get_profile_with_pending_fields(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.patch("/profile", response_model=ResearcherProfileRead)
def update_profile(
    body: ResearcherProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherProfileRead:
    """Modification post-onboarding — ORCID, affiliation, domaines, résumés.
    Voir researcher_profile_service.update_profile pour le détail champ par
    champ (seuls les champs envoyés sont modifiés)."""
    _require_chercheur_role(current_user)
    try:
        researcher_profile_service.update_profile(db, current_user.id, body)
        return researcher_profile_service.get_profile_with_pending_fields(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.delete("/profile/expertise-summary", response_model=ResearcherProfileRead)
def delete_expertise_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherProfileRead:
    _require_chercheur_role(current_user)
    try:
        researcher_profile_service.delete_expertise_summary(db, current_user.id)
        return researcher_profile_service.get_profile_with_pending_fields(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.delete("/profile/research-work-summary", response_model=ResearcherProfileRead)
def delete_research_work_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherProfileRead:
    _require_chercheur_role(current_user)
    try:
        researcher_profile_service.delete_research_work_summary(db, current_user.id)
        return researcher_profile_service.get_profile_with_pending_fields(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)


@router.post("/profile/generer-expertise-summary", status_code=status.HTTP_202_ACCEPTED)
def trigger_expertise_summary(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Génère expertise_summary à partir de researcher_past_expertises.
    Rattrapable indépendamment de research_work_summary — deux boutons
    séparés côté frontend, deux fonctions séparées dans researcher_summary_service,
    un échec sur l'un n'affecte jamais l'autre."""
    _require_chercheur_role(current_user)
    try:
        profile = researcher_profile_service.get_by_user_id(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)

    background_tasks.add_task(researcher_summary_service.generate_expertise_summary, profile.id)
    return {"status": "processing"}


@router.post("/profile/generer-research-work-summary", status_code=status.HTTP_202_ACCEPTED)
def trigger_research_work_summary(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_chercheur_role(current_user)
    try:
        profile = researcher_profile_service.get_by_user_id(db, current_user.id)
    except ResearcherProfileNotFoundError as exc:
        raise _handle_profile_error(exc)

    background_tasks.add_task(researcher_summary_service.generate_research_work_summary, profile.id)
    return {"status": "processing"}
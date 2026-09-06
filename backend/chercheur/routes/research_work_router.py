"""Routes des travaux de recherche — service 0.0.2 (dépôt, extraction async),
0.0.3 (consultation), correction des champs directs, validation des champs
reformulés par LLM.

POST /chercheur/travaux/depot, GET /chercheur/travaux,
PATCH /chercheur/travaux/{work_id}, PATCH /chercheur/travaux/champs/{id}.
"""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.chercheur.schemas.research_work_schemas import ResearchWorkRead, ResearchWorkUpdate
from backend.chercheur.schemas.researcher_field_value_schemas import (
    ResearcherFieldValueRead,
    ResearcherFieldValueValidationAction,
)
from backend.chercheur.services import research_extraction_service, research_work_service
from backend.chercheur.services.research_work_service import (
    ForbiddenError,
    ResearchWorkError,
    ResearchWorkNotFoundError,
)
from backend.chercheur.services.researcher_field_value_service import (
    FieldValueNotFoundError,
    InvalidFieldValueStateError,
)
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/chercheur/travaux", tags=["chercheur-travaux"])


def _require_chercheur_role(current_user: User) -> None:
    if current_user.role != "chercheur":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux comptes chercheur.")


def _handle_work_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ResearchWorkNotFoundError, FieldValueNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/depot", status_code=status.HTTP_202_ACCEPTED)
async def deposit_work(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Dépôt = juste le fichier. Aucun champ saisi à la main : titre, résumé,
    auteurs, venue, DOI sont extraits en tâche de fond (texte du PDF +
    analyse LLM), puis les champs reformulés (résumé, méthodologie...)
    attendent validation humaine.

    202 Accepted : le traitement n'est pas terminé à la réponse — pas de
    research_work créé ici, voir research_extraction_service.run_manual_deposit_extraction.
    file_bytes est lu une seule fois puis transmis à la tâche de fond, pour
    éviter un retéléchargement inutile depuis Cloudinary."""
    _require_chercheur_role(current_user)
    try:
        profile_id = research_work_service.get_researcher_profile_id(db, current_user)
    except ResearchWorkError as exc:
        raise _handle_work_error(exc)

    file_bytes = await file.read()
    file_url = research_work_service.upload_work_file(file_bytes)
    background_tasks.add_task(
        research_extraction_service.run_manual_deposit_extraction, profile_id, file_url, file_bytes
    )
    return {"status": "processing"}


@router.post("/extraire", status_code=status.HTTP_202_ACCEPTED)
def trigger_extraction(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Déclenchement à la demande de l'extraction HAL/OpenAlex — plus de
    lancement automatique à l'onboarding (voir researcher_profile_service).
    Raison : un job qui démarre en tâche de fond juste après l'onboarding,
    sans que le chercheur sache qu'il tourne, le laisse devant une page
    "Mes travaux" vide sans explication le temps que ça se termine.

    202 Accepted : peut créer plusieurs research_works, aucun objet renvoyé
    ici — le frontend détecte la fin par polling de GET /chercheur/travaux,
    même mécanisme que le dépôt manuel."""
    _require_chercheur_role(current_user)
    try:
        profile_id, orcid_id = research_work_service.get_extraction_context(db, current_user)
    except ResearchWorkError as exc:
        raise _handle_work_error(exc)

    background_tasks.add_task(research_extraction_service.run_extraction, profile_id, orcid_id)
    return {"status": "processing"}


@router.post("/{work_id}/regenerer-analyse", status_code=status.HTTP_202_ACCEPTED)
def trigger_analysis_regeneration(
    work_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Rattrapage manuel quand la génération LLM initiale a échoué (rate
    limit Groq typiquement, voir research_extraction_service.py) et qu'un
    travail se retrouve sans aucun champ généré (paper_summary,
    methodology...). Ne relance rien si un résumé n'est pas disponible —
    le LLM n'a rien à analyser sans lui."""
    _require_chercheur_role(current_user)
    try:
        work = research_work_service.get_owned_work(db, current_user, work_id)
    except ResearchWorkError as exc:
        raise _handle_work_error(exc)

    if not work.abstract or not work.abstract.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pas de résumé disponible pour générer une analyse.",
        )

    background_tasks.add_task(
        research_extraction_service.regenerate_analysis, work_id, work.abstract, work.title
    )
    return {"status": "processing"}


@router.get("", response_model=list[ResearchWorkRead])
def list_my_works(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResearchWorkRead]:
    _require_chercheur_role(current_user)
    return research_work_service.list_works_with_pending_fields(db, current_user)


@router.patch("/{work_id}", response_model=ResearchWorkRead)
def update_work(
    work_id: UUID,
    body: ResearchWorkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchWorkRead:
    _require_chercheur_role(current_user)
    try:
        return research_work_service.update_work_fields(db, current_user, work_id, body)
    except ResearchWorkError as exc:
        raise _handle_work_error(exc)


@router.patch("/champs/{field_value_id}", response_model=ResearcherFieldValueRead)
def validate_field(
    field_value_id: UUID,
    body: ResearcherFieldValueValidationAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearcherFieldValueRead:
    _require_chercheur_role(current_user)
    try:
        return research_work_service.validate_field(db, current_user, field_value_id, body.action,body.new_value)
    except (ResearchWorkError, FieldValueNotFoundError, InvalidFieldValueStateError) as exc:
        raise _handle_work_error(exc)
    
    
@router.delete("/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work(
    work_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _require_chercheur_role(current_user)
    try:
        research_work_service.delete_work(db, current_user, work_id)
    except ResearchWorkError as exc:
        raise _handle_work_error(exc)
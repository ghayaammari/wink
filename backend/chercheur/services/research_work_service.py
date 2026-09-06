"""Logique métier — research_works. Dépôt manuel de travaux (service 0.0.2,
déclenche une extraction de fond, pas de saisie manuelle des champs),
consultation avec champs en attente (service 0.0.3), correction des champs
extraits directement, et validation des champs reformulés par LLM via le
mécanisme polymorphe (researcher_field_value_service)."""
import uuid
import os 

from sqlalchemy.orm import Session

from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.schemas.research_work_schemas import ResearchWorkUpdate
from backend.chercheur.services import researcher_field_value_service, researcher_profile_service
from backend.chercheur.services.researcher_field_value_service import FieldValueNotFoundError
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service


class ResearchWorkError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class ResearchWorkNotFoundError(ResearchWorkError):
    """Traduite en 404."""


class ForbiddenError(ResearchWorkError):
    """Traduite en 403 — le travail ciblé n'appartient pas au chercheur connecté."""


def get_owned_work(db: Session, user: User, work_id: uuid.UUID) -> ResearchWork:
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    work = db.get(ResearchWork, work_id)
    if work is None:
        raise ResearchWorkNotFoundError("Travail introuvable.")
    if work.researcher_profile_id != profile.id:
        raise ForbiddenError("Ce travail ne t'appartient pas.")
    return work


def get_researcher_profile_id(db: Session, user: User) -> uuid.UUID:
    """Le router en a besoin pour transmettre l'ID à la tâche de fond
    d'extraction, sans importer researcher_profile_service directement —
    chaque router ne parle qu'à son propre service."""
    return researcher_profile_service.get_by_user_id(db, user.id).id


def get_extraction_context(db: Session, user: User) -> tuple[uuid.UUID, str]:
    """Pour le déclenchement à la demande de l'extraction HAL/OpenAlex
    (bouton "Extraire" — plus de déclenchement automatique à l'onboarding,
    voir research_extraction_service.py). Erreur explicite si pas d'ORCID
    enregistré, plutôt que de laisser un job tourner pour rien en tâche de
    fond et échouer silencieusement côté extraction."""
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    if not profile.orcid_id:
        raise ResearchWorkError("Aucun ORCID enregistré sur ton profil — impossible de lancer l'extraction.")
    return profile.id, profile.orcid_id


def upload_work_file(file_bytes: bytes) -> str:
    """Upload Cloudinary — même mécanisme que upload_project_logo côté
    entrepreneur, pas de logique dupliquée.

    ⚠️ DETTE TECHNIQUE TEMPORAIRE : si SKIP_CLOUDINARY_UPLOAD=true dans .env,
    contourne l'upload réel et renvoie une URL factice — utile pour tester le
    pipeline d'extraction sans Cloudinary configuré. À RETIRER dès que
    CLOUDINARY_CLOUD_NAME est renseigné en local. Ne jamais laisser ce flag
    à true en dehors du dev local (aucun fichier réel n'est stocké nulle
    part, file_url ne pointera vers rien de consultable)."""
    if os.getenv("SKIP_CLOUDINARY_UPLOAD", "false").lower() == "true":
        return "https://placeholder.local/mock-upload.pdf"
    return cloudinary_service.upload_image(file_bytes)


def update_work_fields(db: Session, user: User, work_id: uuid.UUID, data: ResearchWorkUpdate) -> ResearchWork:
    """Permet de corriger les champs extraits directement (titre, résumé,
    auteurs, venue, doi, type de publication) si le VLM s'est trompé. Ces
    champs ne passent pas par researcher_field_values : ils sont factuels,
    pas générés/reformulés, donc une correction directe suffit — pas besoin
    du cycle confirm/reject."""
    work = get_owned_work(db, user, work_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(work, field, value)
    db.commit()
    db.refresh(work)
    work.generated_field_values = researcher_field_value_service.list_all_for_entity(
        db, entity_type="research_work", entity_id=work.id
    )
    return work


def list_works_with_pending_fields(db: Session, user: User) -> list[ResearchWork]:
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    works = db.query(ResearchWork).filter(ResearchWork.researcher_profile_id == profile.id).all()
    for work in works:
       work.generated_field_values = researcher_field_value_service.list_all_for_entity(
    db, entity_type="research_work", entity_id=work.id
)
    return works


def validate_field(
    db: Session, user: User, field_value_id: uuid.UUID, action: str, new_value: str | None = None
) -> ResearcherFieldValue:
    field_value = db.get(ResearcherFieldValue, field_value_id)
    if field_value is None:
        raise FieldValueNotFoundError(f"researcher_field_value {field_value_id} introuvable")

    if field_value.entity_type == "research_work":
        get_owned_work(db, user, field_value.entity_id)
    else:
        profile = researcher_profile_service.get_by_user_id(db, user.id)
        if field_value.entity_id != profile.id:
            raise ForbiddenError("Ce champ ne t'appartient pas.")

    if action == "confirm":
        result = researcher_field_value_service.confirm_value(db, field_value_id)
    elif action == "reject":
        result = researcher_field_value_service.reject_value(db, field_value_id)
    else:  # "edit"
        result = researcher_field_value_service.edit_value(db, field_value_id, new_value)
    db.commit()
    return result
def delete_work(db: Session, user: User, work_id: uuid.UUID) -> None:
    """Supprime le travail ET ses champs extraits associés. researcher_field_values
    n'a pas de vraie FK vers research_works (mécanisme polymorphe, entity_type/
    entity_id) — aucune CASCADE SQL ne s'en charge. Sans ce nettoyage manuel, les
    field_values resteraient orphelins en base après suppression du travail parent.

    Dette technique assumée : le fichier sur Cloudinary (work.file_url) n'est
    pas supprimé ici — pas de méthode delete côté cloudinary_service pour
    l'instant. Acceptable pour l'I0 (stockage gratuit à ce volume), à traiter
    si le nettoyage de stockage devient un sujet."""
    work = get_owned_work(db, user, work_id)
    db.query(ResearcherFieldValue).filter(
        ResearcherFieldValue.entity_type == "research_work",
        ResearcherFieldValue.entity_id == work.id,
    ).delete()
    db.delete(work)
    db.commit()
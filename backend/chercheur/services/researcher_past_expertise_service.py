"""Logique métier — researcher_past_expertises. Ajout et consultation des
expertises passées du chercheur (table facultative, alimente
researcher_profiles.expertise_summary une fois qu'au moins une ligne existe
— génération de ce résumé hors périmètre ici, voir researcher_profile_service).

Pas d'erreur métier dédiée : la seule chose qui peut échouer avant l'écriture
en base est l'absence de profil chercheur pour l'utilisateur connecté, déjà
couverte par ResearcherProfileNotFoundError (researcher_profile_service).
"""
import uuid

from sqlalchemy.orm import Session

from backend.chercheur.models.researcher_past_expertise import ResearcherPastExpertise
from backend.chercheur.schemas.researcher_past_expertise_schemas import PastExpertiseCreate, PastExpertiseUpdate
from backend.chercheur.services import researcher_profile_service
from backend.shared.models.user import User


class PastExpertiseError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class PastExpertiseNotFoundError(PastExpertiseError):
    """Traduite en 404."""


class PastExpertiseForbiddenError(PastExpertiseError):
    """Traduite en 403 — l'expertise ciblée n'appartient pas au chercheur connecté."""


def get_owned_expertise(db: Session, user: User, expertise_id: uuid.UUID) -> ResearcherPastExpertise:
    """Même pattern que get_owned_work côté research_work_service : vérifie
    l'appartenance avant toute lecture/écriture, pas seulement l'existence —
    sinon un chercheur pourrait modifier l'expertise d'un autre en devinant
    un UUID."""
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    expertise = db.get(ResearcherPastExpertise, expertise_id)
    if expertise is None:
        raise PastExpertiseNotFoundError("Expertise introuvable.")
    if expertise.researcher_profile_id != profile.id:
        raise PastExpertiseForbiddenError("Cette expertise ne t'appartient pas.")
    return expertise


def list_for_user(db: Session, user: User) -> list[ResearcherPastExpertise]:
    """Plus récentes en premier — l'ordre de saisie n'a pas de valeur
    métier ici, contrairement à research_works où l'ordre suit la liste
    renvoyée par listMyWorks côté frontend."""
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    return (
        db.query(ResearcherPastExpertise)
        .filter(ResearcherPastExpertise.researcher_profile_id == profile.id)
        .order_by(ResearcherPastExpertise.created_at.desc())
        .all()
    )


def create_for_user(db: Session, user: User, data: PastExpertiseCreate) -> ResearcherPastExpertise:
    profile = researcher_profile_service.get_by_user_id(db, user.id)
    expertise = ResearcherPastExpertise(researcher_profile_id=profile.id, **data.model_dump())
    db.add(expertise)
    db.commit()
    db.refresh(expertise)
    return expertise


def update_for_user(
    db: Session, user: User, expertise_id: uuid.UUID, data: PastExpertiseUpdate
) -> ResearcherPastExpertise:
    """Mise à jour partielle, tous les champs. Pas de workflow de validation
    ici (contrairement aux champs extraits de HAL/OpenAlex via
    researcher_field_values) : une correction directe suffit, la donnée est
    déjà saisie manuellement par le chercheur."""
    expertise = get_owned_expertise(db, user, expertise_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expertise, field, value)
    db.commit()
    db.refresh(expertise)
    return expertise
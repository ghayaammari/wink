"""Logique métier du profil `healthtech_data_profile` — service 3.3.5

(HealthTech). Copie conforme de `ai_act_data_profile_service.py` (get-or-
create + PATCH via exclude_unset), avec une différence : chaque PATCH
déclenche aussi le recalcul de la classification (voir docstring
`project_healthtech_classification_service.py` pour le "pourquoi" de cet
auto-recalcul, absent côté AI Act/RGPD).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.healthtech_data_profile import HealthtechDataProfile
from backend.entrepreneur.schemas.healthtech_data_profile_schemas import HealthtechDataProfileUpdate
from backend.entrepreneur.services.project_healthtech_classification_service import upsert_from_profile
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_profile(db: Session, user: User, project_id: UUID) -> HealthtechDataProfile:
    project = get_owned_project(db, user, project_id)

    profile = db.query(HealthtechDataProfile).filter(HealthtechDataProfile.project_id == project.id).first()
    if profile is None:
        profile = HealthtechDataProfile(project_id=project.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def is_profile_complete(profile: HealthtechDataProfile) -> bool:
    """True si les 4 questions du questionnaire ont une réponse (True/False,

    pas None) — condition de déblocage du 1er chapitre d'analyse d'écart
    (service 3.3.6), voir project_healthtech_gap_analysis_service.py. Ne
    regarde pas si la classification est déterminée (classe_risque non
    nul) : la "porte" est_dispositif_medical peut court-circuiter le calcul
    de classe_risque sans dispenser l'entrepreneur de répondre aux 4
    questions (choix explicite, voir conversation produit).
    """
    return (
        profile.est_dispositif_medical is not None
        and profile.fournit_aide_decision_diagnostique_ou_therapeutique is not None
        and profile.risque_deces_ou_deterioration_irreversible is not None
        and profile.risque_intervention_chirurgicale_ou_deterioration_grave is not None
    )


def update_profile(
    db: Session, user: User, project_id: UUID, data: HealthtechDataProfileUpdate
) -> HealthtechDataProfile:
    profile = get_or_create_profile(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    # Recalcul immediat : calcul deterministe gratuit, pas de raison d'attendre
    # un clic explicite (voir docstring project_healthtech_classification_service.py).
    upsert_from_profile(db, profile.project_id, profile)

    return profile

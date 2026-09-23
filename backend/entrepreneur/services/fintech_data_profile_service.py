"""Logique métier du profil `fintech_data_profile` — service 3.3.5 (FinTech).

Copie conforme de `healthtech_data_profile_service.py` (get-or-create +
PATCH via exclude_unset + recalcul immédiat de la classification), non
répétée ici en détail — voir docstring
`project_fintech_classification_service.py` pour le "pourquoi" de
l'auto-recalcul.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.fintech_data_profile import FintechDataProfile
from backend.entrepreneur.schemas.fintech_data_profile_schemas import FintechDataProfileUpdate
from backend.entrepreneur.services.project_fintech_classification_service import upsert_from_profile
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_profile(db: Session, user: User, project_id: UUID) -> FintechDataProfile:
    project = get_owned_project(db, user, project_id)

    profile = db.query(FintechDataProfile).filter(FintechDataProfile.project_id == project.id).first()
    if profile is None:
        profile = FintechDataProfile(project_id=project.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def is_profile_complete(profile: FintechDataProfile) -> bool:
    """Même rôle que healthtech_data_profile_service.is_profile_complete —

    condition de déblocage de l'unique bloc d'analyse d'écart FinTech (pas
    de chapitres ici, voir project_fintech_gap_analysis_service.py).
    """
    return (
        profile.gere_fonds_ou_paiements_clients is not None
        and profile.volume_mensuel_depasse_3_millions is not None
        and profile.propose_transmission_de_fonds is not None
        and profile.gere_investissement_ou_actifs is not None
    )


def update_profile(db: Session, user: User, project_id: UUID, data: FintechDataProfileUpdate) -> FintechDataProfile:
    profile = get_or_create_profile(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    upsert_from_profile(db, profile.project_id, profile)

    return profile

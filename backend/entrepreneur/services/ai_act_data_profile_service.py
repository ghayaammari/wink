"""Logique métier du profil `ai_act_data_profile` — service 3.3.12 (AI Act).

Copie conforme de `compliance_data_profile_service.py` (get-or-create + PATCH
via exclude_unset), non répétée ici en détail.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.ai_act_data_profile import AiActDataProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.schemas.ai_act_data_profile_schemas import AiActDataProfileUpdate
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_profile(db: Session, user: User, project_id: UUID) -> AiActDataProfile:
    project = get_owned_project(db, user, project_id)

    profile = db.query(AiActDataProfile).filter(AiActDataProfile.project_id == project.id).first()
    if profile is None:
        profile = AiActDataProfile(project_id=project.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def build_profil_context(profile: AiActDataProfile, project: Project) -> dict:
    """Contexte envoyé à l'agent AI Act : réponses du diagnostic (tri-état,

    `None` = pas encore répondu) ET contexte projet déjà connu (secteur,
    description) — même principe que build_profil_context (RGPD, voir
    compliance_data_profile_service.py). `utilise_ia` est inclus pour
    contexte même si le court-circuit `utilise_ia is False` (voir
    ai_act_diagnostic_service.py) empêche cette fonction d'être appelée dans
    ce cas précis.
    """
    return {
        "secteur": project.sector,
        "description_projet": project.description,
        "utilise_ia": profile.utilise_ia,
        "usage_biometrie_ou_identification": profile.usage_biometrie_ou_identification,
        "usage_scoring_emploi_credit_ou_education": profile.usage_scoring_emploi_credit_ou_education,
        "usage_infrastructure_ou_securite_critique": profile.usage_infrastructure_ou_securite_critique,
        "interagit_ou_genere_contenu_pour_utilisateurs": profile.interagit_ou_genere_contenu_pour_utilisateurs,
        "developpe_modele_ia_usage_general": profile.developpe_modele_ia_usage_general,
    }


def update_profile(db: Session, user: User, project_id: UUID, data: AiActDataProfileUpdate) -> AiActDataProfile:
    profile = get_or_create_profile(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile

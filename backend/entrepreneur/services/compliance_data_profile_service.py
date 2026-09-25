"""Logique métier du profil de traitement de données `compliance_data_profile`
— service 3.3.1 (RGPD). Get-or-create + PATCH, même pattern que
`update_legal_profile` (project_service.py) : pas de route Create séparée, la
ligne est créée à la volée dès le premier accès à la carte RGPD (voir
docstring du modèle sur le timing, différent de l'onboarding I0).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.compliance_data_profile import ComplianceDataProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.schemas.compliance_data_profile_schemas import ComplianceDataProfileUpdate
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_profile(db: Session, user: User, project_id: UUID) -> ComplianceDataProfile:
    project = get_owned_project(db, user, project_id)

    profile = db.query(ComplianceDataProfile).filter(ComplianceDataProfile.project_id == project.id).first()
    if profile is None:
        profile = ComplianceDataProfile(project_id=project.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


# Deplace ici le 18/09/2026 depuis rgpd_diagnostic_service.py (etait prive,
# _build_profil_context) : reutilise maintenant aussi par
# aipd_analysis_service.py (service 3.3.4) - ce module possede le modele
# ComplianceDataProfile, c'est le point naturel pour cette fonction plutot
# que de la dupliquer dans chaque service consommateur.
def build_profil_context(profile: ComplianceDataProfile, project: Project) -> dict:
    """Contexte complet envoye a l'agent conformite : les reponses du

    diagnostic RGPD (tri-etat, `None` = pas encore repondu, jamais traite
    comme "non" — voir les prompts compliance_agent_rgpd.*) ET les donnees
    projet deja connues depuis l'onboarding I0 (secteur, description). Sans
    ce contexte projet, l'agent ignorerait par exemple qu'un projet e-sante
    traite quasi certainement des donnees de sante, meme si l'entrepreneur
    n'a pas encore coche la case correspondante dans le diagnostic.
    """
    return {
        "secteur": project.sector,
        "description_projet": project.description,
        "collecte_donnees_sensibles": profile.collecte_donnees_sensibles,
        "collecte_donnees_mineurs": profile.collecte_donnees_mineurs,
        "profilage": profile.profilage,
        "partage_avec_tiers": profile.partage_avec_tiers,
        "transfert_hors_ue": profile.transfert_hors_ue,
    }


def update_profile(
    db: Session, user: User, project_id: UUID, data: ComplianceDataProfileUpdate
) -> ComplianceDataProfile:
    profile = get_or_create_profile(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile

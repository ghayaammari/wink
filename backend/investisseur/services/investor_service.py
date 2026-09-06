"""Service métier — investor_profiles. Parcours linéaire (0.0.2 à 0.0.4) :
un seul appel POST /investisseur/onboarding couvre type d'investisseur,
organisation, thèse, email de contact, calcule profile_completion et
débloque le dashboard. Après ça, PATCH /investisseur/profile (service 0.0.3)
permet de tout modifier librement, y compris repasser à "0%" — le gate ne se
revérifie qu'à l'entrée dans InvestisseurDashboardRoute (frontend), jamais
recalculé côté blocage ici (voir dette technique assumée dans
investor_schemas.py).
"""
import uuid

from sqlalchemy.orm import Session

from backend.investisseur.models.investor_profile import InvestorProfile
from backend.investisseur.schemas.investor_schemas import InvestorOnboardingRequest, InvestorProfileUpdate


class InvestorProfileNotFoundError(Exception):
    pass


def get_by_user_id(db: Session, user_id: uuid.UUID) -> InvestorProfile:
    profile = db.query(InvestorProfile).filter_by(user_id=user_id).first()
    if profile is None:
        # Ne devrait jamais arriver : auth_service crée le profil vide au signup.
        # Si ça arrive quand même, c'est un bug côté auth, pas côté investisseur.
        raise InvestorProfileNotFoundError(f"Aucun investor_profile pour user_id={user_id}")
    return profile


def _compute_completion(profile: InvestorProfile) -> str:
    """organization_name ne compte pas — seuls investor_type,
    investment_thesis et contact_email alimentent le pourcentage (décision
    actée le 06/09/2026, investor_type ajouté aux 2 champs déjà comptés) :
    ce sont les champs qui servent réellement au matching/contact,
    organization_name est une simple précision. 4 paliers pour 3 champs
    comptés : 0/33/67/100%."""
    filled = sum(1 for value in (profile.investor_type, profile.investment_thesis, profile.contact_email) if value)
    return {0: "0%", 1: "33%", 2: "67%", 3: "100%"}[filled]


def complete_onboarding(db: Session, user_id: uuid.UUID, data: InvestorOnboardingRequest) -> InvestorProfile:
    profile = get_by_user_id(db, user_id)

    profile.investor_type = data.investor_type
    profile.organization_name = data.organization_name
    profile.investment_thesis = data.investment_thesis
    profile.contact_email = data.contact_email
    # investor_type est obligatoire côté schéma (InvestorOnboardingRequest),
    # investment_thesis/contact_email validés "au moins un des deux" — donc
    # jamais "0%" en sortie d'onboarding, au minimum "67%".
    profile.profile_completion = _compute_completion(profile)

    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user_id: uuid.UUID, data: InvestorProfileUpdate) -> InvestorProfile:
    profile = get_by_user_id(db, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.profile_completion = _compute_completion(profile)

    db.commit()
    db.refresh(profile)
    return profile
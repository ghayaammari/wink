"""Logique métier de `investment_offers` — dépôt/liste/fermeture d'une offre

d'investissement, scopée à l'investor_profile de l'utilisateur connecté
(jamais à un project_id, contrairement à research_needs côté entrepreneur :
une offre appartient à l'investisseur, pas à une startup précise). Même
convention que research_need_service.py.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.services.investor_service import get_by_user_id
from backend.shared.models.user import User


class InvestmentOfferNotFoundError(Exception):
    pass


def get_owned_offer(db: Session, user: User, offer_id: UUID) -> InvestmentOffer:
    """Vérifie que cette offre appartient bien à l'investor_profile de cet

    utilisateur -- même garde que get_owned_project côté entrepreneur, pour
    qu'un id d'offre deviné ne suffise pas à lire/modifier l'offre d'un
    autre investisseur."""
    profile = get_by_user_id(db, user.id)
    offer = (
        db.query(InvestmentOffer)
        .filter(InvestmentOffer.id == offer_id, InvestmentOffer.investor_profile_id == profile.id)
        .first()
    )
    if offer is None:
        raise InvestmentOfferNotFoundError("Offre introuvable.")
    return offer


def create_offer(
    db: Session,
    user: User,
    titre: str,
    description: str,
    montant_propose: int,
    secteurs_cibles: list[str],
    stades_cibles: list[str],
) -> InvestmentOffer:
    profile = get_by_user_id(db, user.id)
    offer = InvestmentOffer(
        investor_profile_id=profile.id,
        titre=titre,
        description=description,
        montant_propose=montant_propose,
        secteurs_cibles=secteurs_cibles,
        stades_cibles=stades_cibles,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def list_offers(db: Session, user: User) -> list[InvestmentOffer]:
    profile = get_by_user_id(db, user.id)
    return (
        db.query(InvestmentOffer)
        .filter(InvestmentOffer.investor_profile_id == profile.id)
        .order_by(InvestmentOffer.created_at.desc())
        .all()
    )


def update_statut(db: Session, user: User, offer_id: UUID, statut: str) -> InvestmentOffer:
    offer = get_owned_offer(db, user, offer_id)
    offer.statut = statut
    db.commit()
    db.refresh(offer)
    return offer

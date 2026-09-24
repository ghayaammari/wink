"""Logique métier du catalogue des offres d'investissement ouvertes --

lecture brute, sans scoring ni agent, accessible à tout entrepreneur pour
parcourir les offres disponibles avant de lancer le matching (service
6.6.1). Fichier séparé de project_offer_match_service.py (résultat de
matching) et startup_offer_matching_orchestration_service.py (déclenchement
de l'agent) : ici, aucune notion de projet ni d'agent, juste une lecture
publique de `investment_offers`.
"""
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.investment_offer_catalogue_schemas import OfferCatalogueRead
from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.models.investor_profile import InvestorProfile


def list_open_offers(db: Session) -> list[OfferCatalogueRead]:
    """Toutes les offres au statut "ouvert", triées des plus récentes aux

    plus anciennes -- aucune donnée d'identification de l'investisseur
    (nom, email, thèse) n'est exposée, seul `investor_type` pour donner un
    minimum de contexte."""
    rows = (
        db.query(InvestmentOffer, InvestorProfile)
        .join(InvestorProfile, InvestorProfile.id == InvestmentOffer.investor_profile_id)
        .filter(InvestmentOffer.statut == "ouvert")
        .order_by(InvestmentOffer.created_at.desc())
        .all()
    )
    return [
        OfferCatalogueRead(
            id=offer.id,
            titre=offer.titre,
            description=offer.description,
            montant_propose=offer.montant_propose,
            secteurs_cibles=offer.secteurs_cibles,
            stades_cibles=offer.stades_cibles,
            investor_type=investor.investor_type,
            created_at=offer.created_at,
        )
        for offer, investor in rows
    ]

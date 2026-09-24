"""Seed idempotent d'un 2e compte investisseur + 1 offre de financement,

ciblant la logistique/e-commerce -- sert à tester le matching Startup ->
Offres (agents/matching_agent/startup_offer_matching_service.py) avec PLUSIEURS
offres disponibles en base, dont une seule pertinente pour une startup donnée.

Ne recrée AUCUNE startup : réutilise "FretMalin" (déjà seedée par
seed_investment_offer.py, logistique/dernier kilomètre) comme startup de test
principale.

- Offre 1 (seed_investment_offer.py, santé numérique/IA/silver economy) :
  FretMalin doit être EXCLUE -- aucun rapport avec le secteur.
- Offre 2 (ce script, logistique/e-commerce) : FretMalin doit MATCHER FORT --
  correspondance directe secteur + stade.

Ce contraste (une même startup exclue d'une offre et retenue pour une autre)
est le test le plus révélateur : il vérifie que l'agent raisonne bien sur le
contenu de chaque offre plutôt que d'appliquer une règle générique.

Lancement : `python -m backend.investisseur.scripts.seed_investment_offer_2`
depuis `wink/`, APRÈS avoir lancé seed_investment_offer.py au moins une fois
(FretMalin doit déjà exister). Idempotent comme le script précédent.
"""
import logging

from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.schemas.investor_schemas import InvestorProfileUpdate
from backend.investisseur.services import investor_service
from backend.shared.auth.services.auth_service import EmailAlreadyExistsError, signup_with_email
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Même mot de passe de test que seed_investment_offer.py -- convention commune.
TEST_PASSWORD = "WinkInvestisseurTest2026!"

INVESTOR = {
    "email": "zoghlemichayma4+investisseur2.test@gmail.com",
    "first_name": "Marc",
    "last_name": "Dubois",
    "investor_type": "vc",
    "investment_thesis": (
        "Je finance des startups en pre-seed/seed qui modernisent la logistique et le "
        "dernier kilomètre en France : optimisation de tournées, réduction des coûts de "
        "transport et de l'empreinte carbone du e-commerce."
    ),
    "contact_email": "marc.dubois.invest@example.com",
}

OFFER = {
    "titre": "Financement seed -- Logistique du dernier kilomètre & e-commerce",
    "description": (
        "Je cherche à financer 1 à 2 startups en pre-seed/seed qui optimisent la logistique "
        "de livraison pour les e-commerçants ou les transporteurs indépendants : "
        "optimisation de tournées, réduction des kilomètres à vide, baisse des coûts de "
        "transport. Je ne cible pas la santé, l'IA grand public ni les secteurs sans lien "
        "avec le transport de marchandises."
    ),
    "montant_propose": 300_000,
    "secteurs_cibles": ["Logistique et transport de marchandises", "E-commerce", "Supply chain"],
    "stades_cibles": ["pre_seed", "seed"],
}


def _get_or_create_user(db, email: str, first_name: str, last_name: str, role: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is not None:
        logger.info("Compte déjà présent : %s", email)
        return user
    try:
        user = signup_with_email(db, email=email, password=TEST_PASSWORD, role=role, first_name=first_name, last_name=last_name)
    except EmailAlreadyExistsError:
        user = db.query(User).filter(User.email == email.lower()).first()
    else:
        logger.info("Compte %s créé : %s", role, email)
    return user


def _seed_investor(db) -> User:
    user = _get_or_create_user(db, INVESTOR["email"], INVESTOR["first_name"], INVESTOR["last_name"], "investisseur")
    investor_service.update_profile(
        db,
        user.id,
        InvestorProfileUpdate(
            investor_type=INVESTOR["investor_type"],
            investment_thesis=INVESTOR["investment_thesis"],
            contact_email=INVESTOR["contact_email"],
        ),
    )
    logger.info("Profil investisseur à jour pour %s", INVESTOR["email"])
    return user


def _seed_offer(db, investor_user: User) -> None:
    profile = investor_service.get_by_user_id(db, investor_user.id)
    offer = (
        db.query(InvestmentOffer)
        .filter(InvestmentOffer.investor_profile_id == profile.id, InvestmentOffer.titre == OFFER["titre"])
        .first()
    )
    if offer is None:
        offer = InvestmentOffer(investor_profile_id=profile.id, **OFFER)
        db.add(offer)
        logger.info("Offre créée : %s", OFFER["titre"])
    else:
        for field, value in OFFER.items():
            setattr(offer, field, value)
        logger.info("Offre déjà présente -- champs mis à jour : %s", OFFER["titre"])
    db.commit()
    db.refresh(offer)
    logger.info("Offre id=%s prête pour le matching.", offer.id)


def run() -> None:
    db = SessionLocal()
    try:
        investor_user = _seed_investor(db)
        _seed_offer(db, investor_user)
    finally:
        db.close()


if __name__ == "__main__":
    run()

"""Seed idempotent d'un compte investisseur + 3 startups de test + 1 offre

de financement, pour tester le matching Investisseur -> Startup
(agents/matching_agent/investisseur_matching_service.py, service miroir de
chercheur_matching_service.py).

Même logique de choix que seed_startup.py / seed_researchers.py : parmi les
3 startups candidates, 2 doivent matcher l'offre (une FORT, une MOYEN) et
1 doit être clairement exclue -- sert à vérifier que l'agent sait EXCLURE,
pas seulement recommander.

Offre déposée : financement seed pour la santé numérique et l'IA au
service du bien-vieillir (secteurs_cibles + stades_cibles ci-dessous).

- "Écoute" (IA conversationnelle + analyse vocale, silver economy,
  pre_seed) -- match FORT attendu : correspond exactement aux secteurs
  ciblés et au stade.
- "VitalSign" (bracelet connecté + détection de chute par apprentissage
  automatique, seed) -- match MOYEN attendu : santé/silver economy réels,
  mais l'IA y est plus périphérique (traitement de capteurs) que chez
  Écoute (IA conversationnelle en coeur de produit).
- "FretMalin" (optimisation d'itinéraires de livraison B2B, logistique,
  seed) -- AUCUN rapport avec la santé/silver economy/IA affective : sert
  à vérifier que l'agent l'exclut plutôt que de l'inclure "pour ne pas en
  oublier" (règle explicite du system prompt).

Chaque startup est déposée avec un profil projet COMPLET (project_
profile_completion="complet") et intention_levee_fonds=True -- ce sont les
2 conditions du pool de candidats côté investisseur (voir
investisseur_matching_tools_service.py::lister_projets_disponibles). Une
startup incomplète ou sans intention de lever des fonds n'apparaîtrait
jamais dans le matching, quel que soit son secteur.

Lancement : `python -m backend.investisseur.scripts.seed_investment_offer`
depuis `wink/`. Idempotent : email déjà présent -> skip la création du
compte, mais les champs projet/offre sont remis à jour à chaque relance.
"""
import logging

from backend.entrepreneur.schemas.project_public_profile_schemas import ProjectPublicProfileUpdate
from backend.entrepreneur.schemas.project_schemas import ProjectUpdate
from backend.entrepreneur.services import project_service
from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.schemas.investor_schemas import InvestorProfileUpdate
from backend.investisseur.services import investor_service
from backend.shared.auth.services.auth_service import EmailAlreadyExistsError, signup_with_email
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mot de passe de test partagé -- même convention que TEST_PASSWORD dans
# seed_startup.py / seed_researchers.py (à changer si ce compte est un jour
# exposé hors dev).
TEST_PASSWORD = "WinkInvestisseurTest2026!"

INVESTOR = {
    "email": "zoghlemichayma4+investisseur.test@gmail.com",
    "first_name": "Amélie",
    "last_name": "Girard",
    "investor_type": "business_angel",
    "investment_thesis": (
        "J'investis en pre-seed/seed dans la santé numérique et l'intelligence artificielle au "
        "service du bien-vieillir : détection précoce de la fragilité, maintien du lien social, "
        "outils pour les aidants et les EHPAD."
    ),
    "contact_email": "amelie.girard.invest@example.com",
}

OFFER = {
    "titre": "Financement seed -- Santé numérique & IA pour le bien vieillir",
    "description": (
        "Je cherche à financer 1 à 2 startups en pre-seed/seed qui utilisent l'IA ou le traitement "
        "de données de santé pour améliorer le quotidien des personnes âgées ou de leurs aidants : "
        "détection de fragilité, prévention des chutes, lutte contre l'isolement, outils pour les "
        "EHPAD et services d'aide à domicile. Je ne cible pas les sujets santé grand public "
        "généralistes ni les secteurs sans lien avec le bien-vieillir."
    ),
    "montant_propose": 250_000,
    "secteurs_cibles": ["Santé numérique", "Intelligence artificielle", "Silver economy"],
    "stades_cibles": ["pre_seed", "seed"],
}

STARTUPS = [
    {
        "email": "zoghlemichayma4+startup.ecoute@gmail.com",
        "first_name": "Camille",
        "last_name": "Fabre",
        "stage": "pre_seed",
        "localisation": "Paris, France",
        "sector": "Intelligence artificielle conversationnelle",
        "subsectors": ["silver economy", "bien-être social"],
        "customer_segments": ["EHPAD", "services d'aide à domicile", "aidants familiaux"],
        "target_users": ["personnes âgées vivant seules"],
        "nombre_cofondateurs": 2,
        "technologies": [
            "traitement automatique du langage",
            "reconnaissance vocale et analyse de la prosodie",
            "apprentissage automatique",
        ],
        "value_proposition": (
            "Écoute est un compagnon vocal conversationnel destiné aux personnes âgées isolées : "
            "au fil des appels quotidiens, il analyse la voix (prosodie, hésitations, changements de "
            "ton) pour détecter une fatigue, une détresse ou un isolement croissant, et alerte un "
            "aidant si besoin -- sans jamais remplacer un contact humain."
        ),
        "description": (
            "Écoute développe un agent conversationnel vocal pour lutter contre l'isolement des "
            "personnes âgées. Le produit combine un modèle de dialogue empathique (NLP) et un module "
            "d'analyse de la voix qui détecte des signaux faibles de détresse émotionnelle ou de "
            "dégradation de l'état général dans la façon de parler, pas seulement dans le contenu "
            "des phrases."
        ),
        "logo_url": "https://res.cloudinary.com/wink-demo/image/upload/v1/seed/ecoute-logo.png",
        "website_url": "https://ecoute-demo.example.com",
    },
    {
        "email": "zoghlemichayma4+startup.vitalsign@gmail.com",
        "first_name": "Nadia",
        "last_name": "Belkacem",
        "stage": "seed",
        "localisation": "Lyon, France",
        "sector": "Santé numérique",
        "subsectors": ["silver economy", "objets connectés"],
        "customer_segments": ["EHPAD", "résidences seniors"],
        "target_users": ["personnes âgées à mobilité réduite"],
        "nombre_cofondateurs": 3,
        "technologies": [
            "capteurs inertiels (accéléromètre/gyroscope)",
            "apprentissage automatique embarqué",
        ],
        "value_proposition": (
            "VitalSign est un bracelet connecté qui détecte automatiquement les chutes des personnes "
            "âgées grâce à un modèle d'apprentissage automatique embarqué analysant les signaux de "
            "capteurs inertiels, et alerte immédiatement les aidants ou les secours."
        ),
        "description": (
            "VitalSign conçoit un bracelet connecté pour la prévention et la détection de chutes chez "
            "les personnes âgées. Un modèle embarqué, entraîné sur des signaux de capteurs inertiels, "
            "distingue une chute réelle d'un geste brusque anodin pour limiter les fausses alertes, "
            "et transmet une alerte géolocalisée à un aidant désigné."
        ),
        "logo_url": "https://res.cloudinary.com/wink-demo/image/upload/v1/seed/vitalsign-logo.png",
        "website_url": "https://vitalsign-demo.example.com",
    },
    {
        "email": "zoghlemichayma4+startup.fretmalin@gmail.com",
        "first_name": "Julien",
        "last_name": "Roussel",
        "stage": "seed",
        "localisation": "Lille, France",
        "sector": "Logistique et transport de marchandises",
        "subsectors": ["e-commerce", "dernier kilomètre"],
        "customer_segments": ["e-commerçants", "transporteurs indépendants"],
        "target_users": ["gestionnaires logistique B2B"],
        "nombre_cofondateurs": 2,
        "technologies": ["optimisation d'itinéraires", "algorithmes de tournées de véhicules"],
        "value_proposition": (
            "FretMalin optimise automatiquement les tournées de livraison du dernier kilomètre pour "
            "réduire les coûts de transport et les kilomètres à vide des transporteurs indépendants."
        ),
        "description": (
            "FretMalin est une plateforme logistique qui calcule des tournées de livraison optimisées "
            "pour les e-commerçants et transporteurs indépendants, afin de réduire les coûts de "
            "transport et l'empreinte carbone du dernier kilomètre."
        ),
        "logo_url": "https://res.cloudinary.com/wink-demo/image/upload/v1/seed/fretmalin-logo.png",
        "website_url": "https://fretmalin-demo.example.com",
    },
]


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


def _seed_startup(db, spec: dict) -> None:
    user = _get_or_create_user(db, spec["email"], spec["first_name"], spec["last_name"], "entrepreneur")

    project = project_service.get_project_for_user(db, user)
    if project is None:
        project = project_service.create_project(db, user, project_type="not_created", stage=spec["stage"])
        logger.info("Projet créé pour %s", spec["email"])
    else:
        logger.info("Projet déjà présent pour %s -- mise à jour des champs.", spec["email"])

    project_service.update_project(
        db,
        user,
        project.id,
        ProjectUpdate(
            project_type="not_created",
            stage=spec["stage"],
            description=spec["description"],
            sector=spec["sector"],
            subsectors=spec["subsectors"],
            customer_segments=spec["customer_segments"],
            target_users=spec["target_users"],
            nombre_cofondateurs=spec["nombre_cofondateurs"],
            intention_levee_fonds=True,
            technologies=spec["technologies"],
            value_proposition=spec["value_proposition"],
            localisation=spec["localisation"],
        ),
    )
    project_service.upsert_public_profile(
        db,
        user,
        project.id,
        ProjectPublicProfileUpdate(logo_url=spec["logo_url"], website_url=spec["website_url"]),
    )

    project = project_service.get_project_for_user(db, user)
    logger.info(
        "Startup '%s' -- completion=%s, intention_levee_fonds=%s",
        spec["email"],
        project.project_profile_completion,
        project.intention_levee_fonds,
    )


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
        for spec in STARTUPS:
            _seed_startup(db, spec)
        investor_user = _seed_investor(db)
        _seed_offer(db, investor_user)
    finally:
        db.close()


if __name__ == "__main__":
    run()

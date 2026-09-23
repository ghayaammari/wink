"""Seed idempotent d'un compte entrepreneur + projet de test, pour tester
le matching_agent (agents/matching_agent/chercheur_matching_service.py,
service 7.7.2) sur un cas réaliste où 2 des 3 chercheurs de test
(seed_researchers.py, backend/chercheur/scripts/) sont pertinents et le
3e ne l'est pas -- utile pour vérifier que l'agent sait aussi EXCLURE un
candidat, pas seulement en trouver.

Choix du profil (délibéré, pas arbitraire) :
- "Écoute" -- compagnon vocal conversationnel pour lutter contre
  l'isolement des personnes âgées, qui analyse la prosodie de la voix
  (émotion, fatigue, détresse) pour adapter la conversation et alerter un
  aidant si besoin.
- Recoupe directement Laurence Devillers (IA affective, interaction
  humain-machine, agents conversationnels) -- match FORT attendu.
- Recoupe indirectement Stéphane Mallat (traitement du signal,
  apprentissage automatique -- les modèles de reconnaissance d'émotion
  vocale reposent sur ce socle) -- match MOYEN attendu, pas un lien
  aussi direct que Devillers.
- Ne recoupe PAS Olivier Gascuel (bioinformatique, phylogénétique --
  aucun rapport) -- sert à vérifier que l'agent exclut bien un chercheur
  sans lien réel plutôt que de l'inclure "pour ne pas en oublier" (règle
  explicite du system prompt, voir prompts.yaml/matching_agent_chercheur).

Ne dépose AUCUN research_need : c'est à l'entrepreneur de le faire lui-même
depuis /entrepreneur/recherche une fois connecté (demande explicite du
22/09/2026), ce script ne construit que le compte + le projet.

Lancement : `python -m backend.entrepreneur.scripts.seed_startup` depuis
`wink/`. Idempotent (email déjà présent -> skip la création, mais met à
jour la description/les champs du projet à chaque relance -- utile si ce
script est corrigé après un premier passage).
"""
import logging

from backend.entrepreneur.schemas.project_schemas import ProjectUpdate
from backend.entrepreneur.services import project_service
from backend.shared.auth.services.auth_service import EmailAlreadyExistsError, signup_with_email
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mot de passe de test partagé -- même convention que TEST_PASSWORD dans
# seed_researchers.py (à changer si ce compte est un jour exposé hors dev).
TEST_PASSWORD = "WinkEntrepreneurTest2026!"

STARTUP = {
    "email": "zoghlemichayma4+startup.ecoute@gmail.com",
    "first_name": "Camille",
    "last_name": "Fabre",
    "project": {
        "stage": "pre_seed",
        "localisation": "Paris, France",
        "sector": "Intelligence artificielle conversationnelle",
        "subsectors": ["silver economy", "bien-être social"],
        "customer_segments": ["EHPAD", "services d'aide à domicile", "aidants familiaux"],
        "target_users": ["personnes âgées vivant seules"],
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
            "d'analyse de la voix (traitement du signal, apprentissage automatique) qui détecte des "
            "signaux faibles de détresse émotionnelle ou de dégradation de l'état général dans la "
            "façon de parler, pas seulement dans le contenu des phrases. Nous cherchons à valider "
            "scientifiquement notre approche de détection d'émotion par la voix avant de la déployer "
            "en EHPAD pilotes."
        ),
    },
}


def run() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == STARTUP["email"].lower()).first()

        if user is None:
            try:
                user = signup_with_email(
                    db,
                    email=STARTUP["email"],
                    password=TEST_PASSWORD,
                    role="entrepreneur",
                    first_name=STARTUP["first_name"],
                    last_name=STARTUP["last_name"],
                )
            except EmailAlreadyExistsError:
                user = db.query(User).filter(User.email == STARTUP["email"].lower()).first()
            else:
                logger.info("Compte entrepreneur créé : %s", STARTUP["email"])
        else:
            logger.info("Compte déjà présent : %s", STARTUP["email"])

        project = project_service.get_project_for_user(db, user)
        if project is None:
            project = project_service.create_project(db, user, project_type="created", stage=STARTUP["project"]["stage"])
            logger.info("Projet créé pour %s", STARTUP["email"])
        else:
            logger.info("Projet déjà présent pour %s -- mise à jour des champs.", STARTUP["email"])

        update = ProjectUpdate(
            stage=STARTUP["project"]["stage"],
            localisation=STARTUP["project"]["localisation"],
            sector=STARTUP["project"]["sector"],
            subsectors=STARTUP["project"]["subsectors"],
            customer_segments=STARTUP["project"]["customer_segments"],
            target_users=STARTUP["project"]["target_users"],
            technologies=STARTUP["project"]["technologies"],
            value_proposition=STARTUP["project"]["value_proposition"],
            description=STARTUP["project"]["description"],
        )
        project_service.update_project(db, user, project.id, update)
        logger.info("Profil du projet 'Écoute' à jour.")
    finally:
        db.close()


if __name__ == "__main__":
    run()

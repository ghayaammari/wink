"""Seed idempotent de comptes chercheurs de test, avec un ORCID réel et
vérifié pour chacun — objectif : tester le pipeline d'extraction HAL/OpenAlex
(research_extraction_service.run_extraction) et la génération des résumés
(researcher_summary_service) sans passer par le formulaire de signup/
onboarding à la main pour chaque profil.

Lancement : `python -m backend.chercheur.scripts.seed_researchers` depuis
`wink/` (même convention que `seed_roadmap_nodes.py`).

Réutilise intégralement auth_service.signup_with_email (création user +
researcher_profile vide) et researcher_profile_service.complete_onboarding
(orcid_id, affiliation via researcher_field_values, profile_completion et
sync_status) plutôt que d'insérer des lignes à la main : les comptes créés
sont EXACTEMENT dans le même état qu'un vrai signup + onboarding terminé,
sans dupliquer/diverger de cette logique (risque déjà rencontré une fois sur
ce projet avec un import de modèle manquant — voir migration c1a2b3c4d5e6 :
mieux vaut réutiliser le chemin de code existant que le recopier).

Idempotent : un email déjà utilisé est simplement ignoré (log + skip) plutôt
que de faire échouer tout le script — relançable sans risque après ajout de
nouveaux chercheurs dans SEED_RESEARCHERS.

Mot de passe partagé pour tous les comptes de ce seed (test uniquement,
jamais utilisé en prod) : voir TEST_PASSWORD ci-dessous.

Adresses en `zoghlemichayma4+<nom>@gmail.com` (alias Gmail, "+" ignoré par
Gmail — tout arrive dans la même boîte) et non `@wink-test.local` : un
premier essai avec `.local` a échoué à la connexion, ce TLD étant réservé
(RFC 6762, mDNS) et rejeté par la validation email du endpoint /auth/login
(EmailStr / email_validator), alors que ce script, en appelant
auth_service.signup_with_email directement, contourne cette validation à la
création — les comptes existaient en base mais ne pouvaient jamais se
connecter. CLEANUP_LEGACY_EMAILS supprime ces 3 comptes orphelins avant de
recréer avec les bonnes adresses.

Sources des ORCID (vérifiés via idref.fr le 22/09/2026, pas inventés) :
- Laurence Devillers : https://www.idref.fr/12531115X
- Stéphane Mallat     : https://www.idref.fr/05753439X
- Olivier Gascuel     : https://www.idref.fr/068625782

`past_expertise` (researcher_past_expertises, service facultatif jamais
demandé à l'onboarding) : contenu VOLONTAIREMENT FICTIF, demandé
explicitement par l'utilisateur pour tester generate_expertise_summary
(researcher_summary_service) sans attendre une vraie mission de conseil
déclarée. Ces 3 personnes sont réelles (ORCID vérifiés ci-dessus) — chaque
champ organization_name/description est donc marqué "(donnée de test,
fictive)" pour ne jamais pouvoir être lu comme un fait réel sur elles, y
compris si ces données fuitaient hors de l'environnement de dev.
"""
import logging

from backend.chercheur.schemas.researcher_past_expertise_schemas import PastExpertiseCreate
from backend.chercheur.schemas.researcher_profile_schemas import ResearcherOnboardingRequest
from backend.chercheur.services import researcher_past_expertise_service, researcher_profile_service
from backend.shared.auth.services.auth_service import EmailAlreadyExistsError, signup_with_email
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mot de passe de test partagé — à changer si ces comptes sont un jour
# exposés hors d'un environnement de dev.
TEST_PASSWORD = "WinkChercheurTest2026!"

# Comptes créés lors du premier essai (@wink-test.local, TLD réservé,
# inutilisables — voir docstring) : supprimés avant de recréer avec les
# bonnes adresses. CASCADE sur researcher_profiles.user_id nettoie le
# profil lié automatiquement (voir researcher_profile.py, ondelete="CASCADE").
CLEANUP_LEGACY_EMAILS = [
    "laurence.devillers@wink-test.local",
    "stephane.mallat@wink-test.local",
    "olivier.gascuel@wink-test.local",
]

SEED_RESEARCHERS = [
    {
        "email": "zoghlemichayma4+laurence.devillers@gmail.com",
        "first_name": "Laurence",
        "last_name": "Devillers",
        "affiliation": "Sorbonne Université / CNRS-LISN",
        "orcid_id": "0000-0001-9894-172X",
        "research_domains": ["intelligence artificielle", "interaction homme-machine"],
        "past_expertise": {
            "organization_name": "Cabinet de conseil en éthique de l'IA (donnée de test, fictive)",
            "domain": "intelligence artificielle",
            "mission_type": "conseil scientifique",
            "period_label": "2021-2022",
            "description": (
                "Mission de conseil sur l'évaluation éthique de systèmes conversationnels pour des acteurs "
                "industriels. (Donnée fictive, ajoutée uniquement pour tester la génération du résumé "
                "d'expertise — ne reflète pas une mission réelle.)"
            ),
        },
    },
    {
        "email": "zoghlemichayma4+stephane.mallat@gmail.com",
        "first_name": "Stéphane",
        "last_name": "Mallat",
        "affiliation": "Collège de France",
        "orcid_id": "0000-0001-5263-8960",
        "research_domains": ["science des données", "apprentissage automatique"],
        "past_expertise": {
            "organization_name": "Fonds d'investissement deep tech (donnée de test, fictive)",
            "domain": "science des données",
            "mission_type": "conseil scientifique",
            "period_label": "2022-2023",
            "description": (
                "Expertise scientifique sur des projets d'apprentissage automatique appliqué au traitement "
                "du signal, pour l'évaluation technique de startups. (Donnée fictive, ajoutée uniquement pour "
                "tester la génération du résumé d'expertise — ne reflète pas une mission réelle.)"
            ),
        },
    },
    {
        "email": "zoghlemichayma4+olivier.gascuel@gmail.com",
        "first_name": "Olivier",
        "last_name": "Gascuel",
        "affiliation": "CNRS / Institut de Systématique, Évolution, Biodiversité",
        "orcid_id": "0000-0002-9412-9723",
        "research_domains": ["bioinformatique", "phylogénétique"],
        "past_expertise": {
            "organization_name": "Institut de recherche en santé publique (donnée de test, fictive)",
            "domain": "bioinformatique",
            "mission_type": "expertise scientifique",
            "period_label": "2019-2020",
            "description": (
                "Mission d'expertise en phylogénétique appliquée au suivi épidémiologique. (Donnée fictive, "
                "ajoutée uniquement pour tester la génération du résumé d'expertise — ne reflète pas une "
                "mission réelle.)"
            ),
        },
    },
]


def _cleanup_legacy_accounts(db) -> None:
    for email in CLEANUP_LEGACY_EMAILS:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user is not None:
            db.delete(user)
            logger.info("Compte legacy inutilisable supprimé : %s", email)
    db.commit()


def run() -> None:
    db = SessionLocal()
    try:
        _cleanup_legacy_accounts(db)

        for entry in SEED_RESEARCHERS:
            user = db.query(User).filter(User.email == entry["email"].lower()).first()

            if user is None:
                try:
                    user = signup_with_email(
                        db,
                        email=entry["email"],
                        password=TEST_PASSWORD,
                        role="chercheur",
                        first_name=entry["first_name"],
                        last_name=entry["last_name"],
                    )
                except EmailAlreadyExistsError:
                    # Course rare (email pris entre le SELECT ci-dessus et le
                    # signup) -- relire plutot que planter tout le script.
                    user = db.query(User).filter(User.email == entry["email"].lower()).first()
                else:
                    researcher_profile_service.complete_onboarding(
                        db,
                        user.id,
                        ResearcherOnboardingRequest(
                            affiliation=entry["affiliation"],
                            extraction_preference="extraire",
                            orcid_id=entry["orcid_id"],
                            research_domains=entry["research_domains"],
                        ),
                    )
                    logger.info("Créé : %s (%s)", entry["email"], entry["orcid_id"])
            else:
                logger.info("Déjà présent : %s", entry["email"])

            # Idempotent : n'ajoute l'expertise que si ce profil n'en a
            # encore aucune -- relancer le script après un premier passage
            # (comptes déjà créés) ne duplique pas la ligne.
            if not researcher_past_expertise_service.list_for_user(db, user):
                researcher_past_expertise_service.create_for_user(
                    db, user, PastExpertiseCreate(**entry["past_expertise"])
                )
                logger.info("Expertise (test, fictive) ajoutée : %s", entry["email"])
    finally:
        db.close()


if __name__ == "__main__":
    run()

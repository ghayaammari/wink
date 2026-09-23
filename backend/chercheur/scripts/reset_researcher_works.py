"""Script ponctuel — supprime tous les research_works (+ leurs
researcher_field_values liées) des 3 comptes chercheurs de test créés par
seed_researchers.py, et remet leur profil en état "prêt à réextraire"
(sync_status='not_started', last_synced_at=None).

Demandé le 22/09/2026 : repartir de zéro après avoir limité l'extraction à
4 travaux (_MAX_WORKS_PER_EXTRACTION dans research_extraction_service.py) --
run_extraction ne dédoublonne pas par titre/DOI, relancer l'extraction sans
nettoyer d'abord aurait créé des doublons plutôt qu'un complément propre.

Lancement : `python -m backend.chercheur.scripts.reset_researcher_works`
depuis `wink/`. Réutilisable (idempotent par nature : ne fait rien si un
compte n'a déjà plus de travaux), mais n'a pas vocation à devenir un script
permanent -- à supprimer une fois que le nettoyage manuel via le bouton
"Supprimer" par travail (déjà disponible côté frontend) suffit.
"""
import logging

from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.models.researcher_profile import ResearcherProfile
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mêmes 3 comptes que seed_researchers.py (voir ce fichier pour le pourquoi
# de ces adresses en +alias Gmail plutôt que @wink-test.local).
TARGET_EMAILS = [
    "zoghlemichayma4+laurence.devillers@gmail.com",
    "zoghlemichayma4+stephane.mallat@gmail.com",
    "zoghlemichayma4+olivier.gascuel@gmail.com",
]


def run() -> None:
    db = SessionLocal()
    try:
        for email in TARGET_EMAILS:
            user = db.query(User).filter(User.email == email.lower()).first()
            if user is None:
                logger.info("Compte introuvable, ignoré : %s", email)
                continue

            profile = db.query(ResearcherProfile).filter_by(user_id=user.id).first()
            if profile is None:
                logger.info("Pas de researcher_profile pour %s, ignoré.", email)
                continue

            works = db.query(ResearchWork).filter_by(researcher_profile_id=profile.id).all()
            if not works:
                logger.info("Déjà vide, rien à supprimer : %s", email)
            else:
                work_ids = [w.id for w in works]
                db.query(ResearcherFieldValue).filter(
                    ResearcherFieldValue.entity_type == "research_work",
                    ResearcherFieldValue.entity_id.in_(work_ids),
                ).delete(synchronize_session=False)
                db.query(ResearchWork).filter(ResearchWork.id.in_(work_ids)).delete(synchronize_session=False)
                logger.info("%s travail(aux) supprimé(s) : %s", len(work_ids), email)

            # Remet le profil en état "pas encore extrait" -- sinon la page
            # "Mes travaux" resterait sur sync_status='completed' d'une
            # extraction précédente, trompeur une fois les travaux effacés.
            profile.sync_status = "not_started"
            profile.last_synced_at = None
            db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    run()

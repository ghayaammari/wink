"""Test manuel ponctuel — PAS un fichier du projet, à supprimer une fois le

test fait. Vérifie run_chapter_diagnostic() (service 3.3.6, volet
HealthTech) en conditions réelles : vraie recherche vectorielle sur
content_embeddings (domaine='secteur_healthtech', 110 articles MDR
collectés), vraie classification HealthTech en base, vrai appel Groq via
l'agent, et persistance via upsert_result.

Objectif spécifique : vérifier que le verrouillage des chapitres fonctionne
(le 2e chapitre doit être rejeté tant que le 1er n'a pas de résultat) et que
la génération produit des obligations réellement grounded dans les chunks
MDR récupérés (pas une liste vide, pas une hallucination hors-sujet).

Usage (depuis wink/, venv activé) :
  python _manual_test_healthtech_gap_analysis.py <email> [project_id] [chapitre]

Si project_id est omis, liste les projets HealthTech déjà classifiés de cet
utilisateur et s'arrête (pour récupérer un id à coller dans un 2e appel).
chapitre par défaut : obligations_fabricant (1er chapitre, toujours débloqué).
"""
import sys
from uuid import UUID

from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_healthtech_classification import ProjectHealthtechClassification
from backend.entrepreneur.services.healthtech_gap_analysis_diagnostic_service import run_chapter_diagnostic
from backend.entrepreneur.services.project_healthtech_gap_analysis_service import get_chapter_status_list
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

if len(sys.argv) < 2:
    print("Usage: python _manual_test_healthtech_gap_analysis.py <email> [project_id] [chapitre]")
    sys.exit(1)

email = sys.argv[1]
project_id_arg = sys.argv[2] if len(sys.argv) > 2 else None
chapitre = sys.argv[3] if len(sys.argv) > 3 else "obligations_fabricant"

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print(f"Aucun utilisateur avec l'email {email}")
        sys.exit(1)

    if project_id_arg is None:
        profile = db.query(EntrepreneurProfile).filter(EntrepreneurProfile.user_id == user.id).first()
        if profile is None:
            print("Aucun entrepreneur_profile pour cet utilisateur.")
            sys.exit(1)
        projects = db.query(Project).filter(Project.entrepreneur_profile_id == profile.id).all()
        if not projects:
            print("Cet utilisateur n'a aucun projet.")
            sys.exit(1)
        print("Projets avec une classification HealthTech :")
        found = False
        for p in projects:
            classification = (
                db.query(ProjectHealthtechClassification)
                .filter(ProjectHealthtechClassification.project_id == p.id)
                .first()
            )
            if classification is not None:
                found = True
                print(
                    f"  id={p.id}  description={p.description}  "
                    f"classe_risque={classification.classe_risque}"
                )
        if not found:
            print("  (aucun — passe d'abord par le questionnaire HealthTech côté frontend pour un projet.)")
        print("\nRelance avec: python _manual_test_healthtech_gap_analysis.py <email> <project_id> [chapitre]")
        sys.exit(0)

    project_id = UUID(project_id_arg)

    print("Statut des chapitres avant génération :")
    for status_item in get_chapter_status_list(db, user, project_id):
        print(f"  {status_item.cle}: {status_item.statut}")

    print(f"\nAppel run_chapter_diagnostic('{chapitre}') (recherche vectorielle réelle + Groq)...")
    result = run_chapter_diagnostic(db, user, project_id, chapitre)

    print(f"\nRésultat persisté pour '{chapitre}' :")
    print("justification:", result.justification)
    print(f"\n{len(result.obligations.get('obligations', []))} obligation(s) :")
    for o in result.obligations.get("obligations", []):
        print("---")
        print("nom:", o.get("nom"))
        print("source_id:", o.get("source_id"))
        print("description:", o.get("description", "")[:150], "...")

    print("\nStatut des chapitres après génération :")
    for status_item in get_chapter_status_list(db, user, project_id):
        print(f"  {status_item.cle}: {status_item.statut}")
finally:
    db.close()

"""Test de bout en bout du compliance_agent le plus simple (sector_detection)
sur le projet de seed "Écoute" (backend/entrepreneur/scripts/seed_startup.py,
déjà exécuté sur cette machine) -- objectif double :

1. Vérifier qu'un vrai appel Groq via create_react_agent (LangGraph) fonctionne
   de bout en bout -- jamais testé jusqu'ici (voir Wink_compliance_agent_recap.md,
   §7 "Non testé de bout en bout").
2. Vérifier si LANGSMITH_TRACING=true (backend/.env, juste active) produit
   enfin une trace visible sur smith.langchain.com/o/.../projects/p/wink --
   contrairement a l'evaluation retrieval (evaluate_retrieval_langsmith.py),
   qui n'appelle jamais Groq/LangGraph et ne peut donc jamais produire de trace :
   ici on a un vrai ChatGroq + create_react_agent, exactement ce que le tracing
   automatique LangChain/LangGraph est censé intercepter sans code supplémentaire.

Lancement : depuis wink/, venv actif : python test_agent_langsmith.py
"""
from dotenv import load_dotenv

load_dotenv("backend/.env")

import os

from backend.entrepreneur.services.sector_detection_diagnostic_service import run_detection
from backend.entrepreneur.services.project_service import get_project_for_user
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

STARTUP_EMAIL = "zoghlemichayma4+startup.ecoute@gmail.com"


def main() -> None:
    print(f"LANGSMITH_TRACING = {os.getenv('LANGSMITH_TRACING')}")
    print(f"LANGSMITH_PROJECT = {os.getenv('LANGSMITH_PROJECT')}")
    print(f"LANGSMITH_ENDPOINT = {os.getenv('LANGSMITH_ENDPOINT')}")
    print()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == STARTUP_EMAIL.lower()).first()
        if user is None:
            print(f"Aucun utilisateur trouve pour {STARTUP_EMAIL} -- lance d'abord :")
            print("  python -m backend.entrepreneur.scripts.seed_startup")
            return

        project = get_project_for_user(db, user)
        if project is None:
            print("Utilisateur trouve mais aucun projet -- relance le seed.")
            return

        print(f"Projet de test : {project.id} (secteur declare : {project.sector})")
        print("Appel de run_detection() -- 1 seul appel Groq attendu...\n")

        result = run_detection(db, user, project.id)

        print("=== Resultat ===")
        print(f"Secteur detecte : {result.secteur_detecte}")
        print(f"Justification   : {result.justification}")
        print("\nSi LANGSMITH_TRACING=true et que la trace apparait sur")
        print("smith.langchain.com (projet 'wink'), le tracing fonctionne enfin.")
        print("Si rien n'apparait apres ce run reussi, le probleme est bien cote")
        print("compte/cle LangSmith, pas cote code -- a confirmer avec toi.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

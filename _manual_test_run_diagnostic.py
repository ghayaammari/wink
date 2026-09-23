"""Test manuel ponctuel — PAS un fichier du projet, a supprimer une fois le
test fait. Verifie run_diagnostic() en conditions reelles : vraie recherche
vectorielle sur content_embeddings (domaine='rgpd'), vrai profil en base,
vrai appel Groq via l'agent, et persistance via sync_obligations.

Objectif specifique de ce test : verifier le CORRECTIF _THEMES_SOCLE — un
profil vide (aucune case cochee) doit quand meme remonter des obligations de
base (registre, base legale, information, securite), pas une liste vide.

Usage (depuis wink/, venv active) :
  python _manual_test_run_diagnostic.py <email> [project_id]

Si project_id est omis, liste les projets de cet utilisateur et s'arrete
(pour recuperer un id a coller dans un 2e appel).
"""
import sys
from uuid import UUID

from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.shared.database import SessionLocal
from backend.shared.models.user import User
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.compliance_data_profile import ComplianceDataProfile
from backend.entrepreneur.services.rgpd_diagnostic_service import run_diagnostic

if len(sys.argv) < 2:
    print("Usage: python _manual_test_run_diagnostic.py <email> [project_id]")
    sys.exit(1)

email = sys.argv[1]
project_id_arg = sys.argv[2] if len(sys.argv) > 2 else None

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print(f"Aucun utilisateur avec l'email {email}")
        sys.exit(1)

    if project_id_arg is None:
        # Un projet appartient a un entrepreneur_profile, pas directement a un
        # user (voir get_owned_project dans project_service.py).
        profile = db.query(EntrepreneurProfile).filter(EntrepreneurProfile.user_id == user.id).first()
        if profile is None:
            print("Aucun entrepreneur_profile pour cet utilisateur.")
            sys.exit(1)
        projects = db.query(Project).filter(Project.entrepreneur_profile_id == profile.id).all()
        if not projects:
            print("Cet utilisateur n'a aucun projet.")
            sys.exit(1)
        print("Projets disponibles :")
        for p in projects:
            print(f"  id={p.id}  type={p.project_type}  stage={p.stage}  description={p.description}")
        print("\nRelance avec: python _manual_test_run_diagnostic.py <email> <project_id>")
        sys.exit(0)

    project_id = UUID(project_id_arg)

    # Optionnel : force un profil vide avant le test, pour verifier
    # specifiquement le comportement "aucune case cochee" -> obligations de
    # base quand meme generees. Decommenter si besoin :
    #
    # profile = db.query(ComplianceDataProfile).filter(
    #     ComplianceDataProfile.project_id == project_id
    # ).first()
    # if profile:
    #     for champ in [
    #         "collecte_donnees_sensibles", "collecte_donnees_mineurs",
    #         "profilage", "partage_avec_tiers", "transfert_hors_ue",
    #     ]:
    #         setattr(profile, champ, None)
    #     db.commit()
    #     print("Profil reinitialise a vide (tous les champs a None).")

    print("Appel run_diagnostic() (recherche vectorielle reelle + Groq)...")
    obligations = run_diagnostic(db, user, project_id)

    print(f"\n{len(obligations)} obligation(s) persistee(s) :\n")
    for o in obligations:
        print("---")
        print("nom:", o.nom)
        print("statut:", o.statut)
        print("legal_text_id:", o.legal_text_id)
        print("description:", o.description[:150], "...")
finally:
    db.close()

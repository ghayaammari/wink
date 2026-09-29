"""Test agentique complet -- diagnostic RGPD sur un projet reel de la base.
Lancement : depuis wink/, venv actif :
  python list_projects_for_test.py          (pour recuperer un project_id)
  python test_agent_rgpd_full.py <project_id>
"""
import logging
import sys
from uuid import UUID

from dotenv import load_dotenv
load_dotenv("backend/.env")

logging.basicConfig(level=logging.INFO, format="%(message)s")

from agents.compliance_agent.rgpd_service import generate_rgpd_obligations
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.shared.database import SessionLocal
from backend.shared.models.user import User

if len(sys.argv) != 2:
    print("Usage : python test_agent_rgpd_full.py <project_id>")
    sys.exit(1)

project_id = UUID(sys.argv[1])
db = SessionLocal()

project = db.query(Project).filter(Project.id == project_id).first()
if project is None:
    print("Projet introuvable.")
    sys.exit(1)

profile = db.query(EntrepreneurProfile).filter(EntrepreneurProfile.id == project.entrepreneur_profile_id).first()
user = db.query(User).filter(User.id == profile.user_id).first()

seen_source_ids: list[str] = []
tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)

print("Lancement de l'agent (peut prendre plusieurs secondes, appels Groq)...")
result = generate_rgpd_obligations(tools)

print(f"\n{len(result.obligations)} obligation(s) generee(s) :\n")
for o in result.obligations:
    print("---")
    print("nom:", o.nom)
    print("description:", o.description[:200])

print(f"\nChunks reellement consultes pendant le run : {seen_source_ids}")
db.close()

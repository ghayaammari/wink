"""Liste les projets existants (id, secteur, stage) pour choisir un project_id
a passer a test_agent_rgpd_full.py.
Lancement : depuis wink/, venv actif : python list_projects_for_test.py
"""
from dotenv import load_dotenv
load_dotenv("backend/.env")

from backend.entrepreneur.models.project import Project
from backend.shared.database import SessionLocal

db = SessionLocal()
projects = db.query(Project).all()
if not projects:
    print("Aucun projet en base.")
for p in projects:
    print(f"{p.id}  |  secteur={p.sector}  |  stage={p.stage}  |  type={p.project_type}")
db.close()
